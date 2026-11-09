#!/usr/bin/env python3
"""Rebuild the IdeaMille Top 100 pages from the weekly site feed CSV (one command).

    python3 tools/refresh_top_ideas.py                 # uses the stable feed path below
    python3 tools/refresh_top_ideas.py FEED.csv        # or a local CSV / published-CSV https URL
    python3 tools/refresh_top_ideas.py --check-links   # also checks every source_url (reports, never drops)
    python3 tools/refresh_top_ideas.py --dry-run       # validate only, write nothing

Default feed: $IDEAMILLE_FEED, else /workspace/ideamille-site/IdeaMille Top 100 Site Feed.csv
(overwritten weekly, Fridays about 6 PM ET; dated copies live in its archive/ folder).

What it writes (all static, GitHub Pages compatible):
  data/top-ideas.json   public fields only: rank, name, sector, region, stage, description, url, origin
  html/top-ideas.html   the full ranked list, pre-rendered between IM-TOP100 markers (works without JS);
                        assets/top100.js adds search and sector / region / origin filters
  html/ideabase.html    "This Week's Top 10" (ranks 1-10) between IM-TOP10 markers
  index.html            home-page Top Ideas callout between IM-TOP-CALLOUT markers

It fails loudly (exit 2, nothing written) if the feed's column header changes in any way, if ranks are
not 1..N without gaps, if a row is not review_status=reviewed, if ranked_date differs between rows,
or if idea_origin has an unknown value. Columns that are not on the public list are never written
anywhere, and the outputs are scanned afterwards to prove it.
Nothing goes live until the changed files are committed and pushed, which needs Michael's OK.
"""
import argparse, csv, datetime, hashlib, html, io, json, os, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_FEED = os.environ.get('IDEAMILLE_FEED', '/workspace/ideamille-site/IdeaMille Top 100 Site Feed.csv')
# Exact header (11 columns, in order) is pinned by hash; any rename, addition, removal or reorder fails.
HEADER_SHA256 = '3616080dfe8b3d37e65f6a8a3df133339a4c28271b500b6f4a571a5ea8c6c47d'  # pinned 2026-11-01 (feed v1.1); re-pin only for a deliberate change
PUBLIC = ['rank', 'name', 'sector', 'region', 'stage', 'public_description', 'source_url', 'ranked_date', 'idea_origin']
ORIGINS = {'live company': ('company', ''), 'former company': ('former', 'Former company'), 'concept': ('concept', 'Concept')}
EXPECTED_ROWS = 100

SECTOR_GROUPS = [
    ('AI, software & data', r'\bai\b|software|saas|devtools|\bdata\b|analytics|agent|cyber|security|computing|intel'),
    ('Robotics, hardware & industry', r'robot|drone|hardware|manufactur|materials|industrial|\b3d\b|aerospace|rocket|\bspace\b|inspection|defense'),
    ('Health & life sciences', r'health|biotech|bioscience|\bmedtech|pharma|clinical|menopause|stem cell|\borgan\b|mental|wellness|therap|sleep|pediatric|diagnostic|alzheimer|medical'),
    ('Fintech', r'fintech|financ|banking infra|credit|m&a|payment|insur|crypto|stablecoin|trading'),
    ('Energy, climate & sustainability', r'energy|climate|battery|solar|carbon|insulation|cleantech|pfas|sustainab'),
    ('Consumer, food & lifestyle', r'consumer|beverage|food|protein|kids|cooler|matcha|outdoor|collectibles|restaurant|wellness|baby'),
    ('Media, creators & entertainment', r'media|entertainment|music|news|creator|animation|film|audio|dubbing'),
    ('Real estate & construction', r'proptech|construction|site-selection|real estate|homebuild|\bhoa\b|building'),
    ('Government, legal & civic', r'govtech|legal|\blaw\b|\bip\b|civic|community resilience'),
    ('Commerce & supply chain', r'commerce|marketplace|supply|trade|logistic|merchant|packaging'),
    ('Education & talent', r'\bedtech|\bed\b|education|hr tech|manager development'),
    ('Ventures & innovation', r'venture studio|innovation|acceleration'),
]
REGION_ORDER = ['North Carolina', 'South Carolina', 'Texas', 'California', 'New York', 'Other United States',
                'Europe', 'Asia', 'Not location-specific', 'Other']
US_CODES = {'NC': 'North Carolina', 'SC': 'South Carolina', 'TX': 'Texas', 'CA': 'California', 'NY': 'New York'}
EUROPE = r'\b(DE|CH|AT|UK|FR|NL|SE|ES|IT|IE|DK|FI|NO|PL)\b|london|berlin|munich|vienna|zurich|stuttgart|paris|amsterdam'
ASIA = r'india|singapore|jakarta|bengaluru|bangalore|indonesia|japan|tokyo|china|korea|seoul|vietnam|malaysia|thailand|philippines'

def die(msg):
    sys.stderr.write('\nREFRESH FAILED - nothing was written.\n' + msg + '\n\n'); sys.exit(2)

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def esc(s): return html.escape(s, quote=True)

def sector_groups(sector):
    s = sector.lower(); return [n for n, p in SECTOR_GROUPS if re.search(p, s)] or ['Other']

def _region(p):
    if 'North Carolina' in p: return 'North Carolina'
    if 'South Carolina' in p: return 'South Carolina'
    if re.search(r'california|los angeles|san francisco|santa monica|silicon valley', p, re.I): return 'California'
    m = re.search(r'\b(NC|SC|TX|CA|NY)\b', p)
    if m: return US_CODES[m.group(1)]
    if re.search(EUROPE, p, re.I): return 'Europe'
    if re.search(ASIA, p, re.I): return 'Asia'
    if re.search(r'united states|\bUSA?\b', p, re.I): return 'Other United States'
    return 'Other'

def region_group(region):
    """Primary location only: text before "(" and, for "A / B", the first place if it is recognisable."""
    p = region.split('(')[0].strip()
    if not p: return 'Not location-specific'
    first = _region(p.split(' / ')[0])
    return first if first != 'Other' else _region(p)

def read_feed(src):
    if src.startswith('http'):
        raw = urllib.request.urlopen(urllib.request.Request(src, headers={'User-Agent': 'ideamille-refresh'}), timeout=60).read().decode('utf-8-sig')
    else:
        if not os.path.exists(src): die(f'Feed not found: {src}')
        raw = open(src, encoding='utf-8-sig').read()
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows: die('Feed is empty.')
    return [h.strip() for h in rows[0]], rows[1:]

def header_hash(header): return hashlib.sha256(','.join(header).encode()).hexdigest()

def validate(header, body):
    got = header_hash(header)
    if got != HEADER_SHA256:
        die('The feed column header changed, so the page build was stopped.\n'
            f'  header found ({len(header)} columns): {", ".join(header)}\n'
            f'  expected: 11 columns in the agreed order, with these public ones: {", ".join(PUBLIC)}\n'
            f'  header hash found {got[:12]}..., expected {HEADER_SHA256[:12]}...\n'
            'Check the change with the feed owner, then update PUBLIC / HEADER_SHA256 in this script (--pin).')
    idx = {h: i for i, h in enumerate(header)}
    rows, problems = [], []
    for n, r in enumerate(body, 2):
        if not any(c.strip() for c in r): continue
        if len(r) != len(header): problems.append(f'line {n}: {len(r)} cells, expected {len(header)}'); continue
        d = {k: r[idx[k]].strip() for k in PUBLIC}
        if r[idx['review_status']].strip().lower() != 'reviewed':
            problems.append(f'line {n}: review_status is not "reviewed"')
        if not d['rank'].isdigit(): problems.append(f'line {n}: rank "{d["rank"]}" is not a whole number')
        if not d['name']: problems.append(f'line {n}: empty name')
        if d['idea_origin'].lower() not in ORIGINS: problems.append(f'line {n}: unknown idea_origin "{d["idea_origin"]}"')
        if d['source_url'] and not d['source_url'].startswith('https://'): problems.append(f'line {n}: source_url is not https: {d["source_url"]}')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', d['ranked_date']): problems.append(f'line {n}: ranked_date "{d["ranked_date"]}" is not YYYY-MM-DD')
        rows.append(d)
    if problems: die('Feed rows failed validation:\n  ' + '\n  '.join(problems))
    ranks = sorted(int(d['rank']) for d in rows)
    if ranks != list(range(1, len(rows) + 1)):
        missing = sorted(set(range(1, max(ranks) + 1)) - set(ranks)); dup = sorted({x for x in ranks if ranks.count(x) > 1})
        die(f'Ranks must run 1..N with no gaps or repeats (missing: {missing or "none"}; repeated: {dup or "none"}).')
    if len(rows) != EXPECTED_ROWS: die(f'Expected {EXPECTED_ROWS} rows, found {len(rows)} (use --expect N if the list size changed on purpose).')
    names = [d['name'].lower() for d in rows]
    if len(set(names)) != len(names): die('Duplicate names in the feed.')
    dates = {d['ranked_date'] for d in rows}
    if len(dates) != 1: die(f'ranked_date differs between rows: {sorted(dates)}')
    rows.sort(key=lambda d: int(d['rank']))
    return rows, dates.pop()

def build(rows):
    ideas = []
    for d in rows:
        okey, label = ORIGINS[d['idea_origin'].lower()]
        ideas.append(dict(rank=int(d['rank']), name=d['name'], sector=d['sector'], region=d['region'], stage=d['stage'],
                          description=d['public_description'], url=d['source_url'], origin=okey, origin_label=label,
                          sector_groups=sector_groups(d['sector']), region_group=region_group(d['region'])))
    return ideas

def options(values, order=None):
    from collections import Counter
    c = Counter(values); keys = [k for k in (order or sorted(c)) if k in c]
    keys = [k for k in keys if k != 'Other'] + (['Other'] if 'Other' in c else [])
    return ''.join(f'<option value="{slug(k)}">{esc(k)} ({c[k]})</option>' for k in keys)

def name_html(i):
    n = esc(i['name'])
    if i['url']:
        n = (f'<a href="{esc(i["url"])}" target="_blank" rel="noopener" title="Opens in a new tab">{n}'
             '<span class="im-ext" aria-hidden="true">&#8599;</span><span class="im-sr"> (opens in a new tab)</span></a>')
    if i['origin_label']:
        n += f' <span class="im-origin im-origin-{i["origin"]}">{esc(i["origin_label"])}</span>'
    return n

def render_list(ideas, label):
    items = []
    for i in ideas:
        meta = [f'<span class="im-t100-sector">{esc(i["sector"])}</span>'] if i['sector'] else []
        if i['region']: meta.append(esc(i['region']))
        if i['stage'] and i['stage'].lower() != i['origin_label'].lower(): meta.append(esc(i['stage']))
        items.append(
            f'  <li class="im-t100-item" id="rank-{i["rank"]}" data-sg="{" ".join(slug(g) for g in i["sector_groups"])}" '
            f'data-rg="{slug(i["region_group"])}" data-origin="{i["origin"]}">'
            f'<span class="im-t100-rank" aria-label="Rank {i["rank"]}">{i["rank"]}</span><div class="im-t100-body">'
            f'<h3 class="im-t100-name">{name_html(i)}</h3>'
            + (f'<p class="im-t100-meta">{" &middot; ".join(meta)}</p>' if meta else '')
            + (f'<p class="im-t100-desc">{esc(i["description"])}</p>' if i['description'] else '')
            + '</div></li>')
    n = len(ideas)
    origins = [i['origin'] for i in ideas]
    ocount = {k: origins.count(k) for k in ('company', 'former', 'concept')}
    oopts = ''.join(f'<option value="{k}">{lab} ({ocount[k]})</option>' for k, lab in
                    (('company', 'Companies'), ('former', 'Former companies'), ('concept', 'Concepts')) if ocount[k])
    return f'''<!-- IM-TOP100:BEGIN (generated by tools/refresh_top_ideas.py; edit the feed, not this block) -->
<div id="top-ideas" class="im-t100">
 <h1 class="im-t100-h">Top {n} Ideas <span>&ndash; the Cream Rising to the Top</span></h1>
 <p class="im-t100-intro">The top {n} opportunities from TechVest&rsquo;s weekly ranking of the ideaMille 1000: companies, former companies and concepts worth building on. Browse the <a href="ideabase.html">ideaBase</a>, or add yours with the <a href="../assets/forms/IdeaMille%20North%20Carolina%20Idea%20Form.pdf">North Carolina idea form</a>.</p>
 <p class="im-t100-ranked"><time datetime="{label[0]}">Ranked {label[1]}</time> &middot; refreshed weekly</p>
 <form class="im-t100-tools" id="t100-tools" role="search" hidden onsubmit="return false">
  <label class="im-t100-search"><span>Search</span><input type="search" id="t100-q" placeholder="Name, sector, place or keyword" autocomplete="off"></label>
  <label><span>Sector</span><select id="t100-sector"><option value="">All sectors</option>{options([g for i in ideas for g in i["sector_groups"]], [g for g, _ in SECTOR_GROUPS])}</select></label>
  <label><span>Region</span><select id="t100-region"><option value="">All regions</option>{options([i["region_group"] for i in ideas], REGION_ORDER)}</select></label>
  <label><span>Type</span><select id="t100-origin"><option value="">All types</option>{oopts}</select></label>
  <button type="button" id="t100-reset">Clear</button>
  <p class="im-t100-count" id="t100-count" aria-live="polite">Showing all {n}</p>
 </form>
 <ol class="im-t100-list" id="t100-list">
{chr(10).join(items)}
 </ol>
 <p class="im-t100-empty" id="t100-empty" hidden>No ideas match those filters. <button type="button" id="t100-reset2">Show all {n}</button></p>
 <p class="im-t100-note">Names link to each company&rsquo;s site or a public source, in a new tab. Rankings are TechVest&rsquo;s opinion, not investment advice.</p>
</div>
<script src="../assets/top100.js" defer></script>
<!-- IM-TOP100:END -->'''

def render_top10(ideas, label):
    cards = []
    for i in ideas[:10]:
        cards.append(f'  <div class="im-idea im-t10-card"><span class="im-t10-rank">{i["rank"]}</span> <strong>{name_html(i)}</strong>'
                     + (f'<span class="im-t10-sector">{esc(i["sector"])}</span>' if i['sector'] else '') + '</div>')
    return f'''<!-- IM-TOP10:BEGIN (generated by tools/refresh_top_ideas.py) -->
<div id="ideabase-top" class="im-ideas im-t10">
 <h2 class="im-t10-h">This Week&rsquo;s Top 10 &ndash; <a href="top-ideas.html">see all Top {len(ideas)}</a></h2>
 <p class="im-t100-ranked"><time datetime="{label[0]}">Ranked {label[1]}</time></p>
 <div id="ideabase-top-grid" class="im-ideas-grid">
{chr(10).join(cards)}
 </div>
</div>
<!-- IM-TOP10:END -->'''

def render_callout(ideas, label):
    return (f'<!-- IM-TOP-CALLOUT:BEGIN --><div class="im-top-callout"><a href="html/top-ideas.html"><b>Top {len(ideas)} Ideas</b> &ndash; '
            f'TechVest&rsquo;s weekly ranking, {label[1]} &raquo;</a> &nbsp;|&nbsp; <a href="html/ideabase.html">ideaBase</a></div><!-- IM-TOP-CALLOUT:END -->')

def splice(path, marker, block):
    t = path.read_text(encoding='utf-8')
    pat = re.compile(r'<!-- ' + marker + r':BEGIN.*?<!-- ' + marker + r':END -->', re.S)
    if not pat.search(t): die(f'{path.relative_to(ROOT)}: markers <!-- {marker}:BEGIN/END --> not found.')
    return pat.sub(lambda m: block, t, count=1)

def check_links(ideas):
    bad = []
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
    for i in ideas:
        if not i['url']: print(f'  #{i["rank"]} {i["name"]}: no link (shown without one)'); continue
        try:
            r = urllib.request.urlopen(urllib.request.Request(i['url'], headers={'User-Agent': ua, 'Accept': 'text/html'}), timeout=25)
            code = r.status
        except urllib.error.HTTPError as e: code = e.code
        except Exception as e: code = f'error: {type(e).__name__}: {str(e)[:80]}'
        if code != 200: bad.append((i['rank'], i['name'], i['url'], code))
    for b in bad: print('  NOT OK  #%s %s  %s  -> %s' % b)
    print(f'  link check: {len(ideas) - len(bad)} of {len(ideas)} rows OK or unlinked; {len(bad)} to review (rows are kept).')

def main():
    global EXPECTED_ROWS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('feed', nargs='?', default=DEFAULT_FEED)
    ap.add_argument('--check-links', action='store_true'); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--expect', type=int, default=EXPECTED_ROWS)
    ap.add_argument('--pin', action='store_true', help='print the hash of the current feed header (for a deliberate header change)')
    a = ap.parse_args(); EXPECTED_ROWS = a.expect
    header, body = read_feed(a.feed)
    if a.pin: print(header_hash(header)); return
    rows, ranked = validate(header, body)
    dt = datetime.date.fromisoformat(ranked); label = (ranked, f'{dt.day} {dt.strftime("%B %Y")}')
    ideas = build(rows)
    for i in ideas:
        if 'Other' in i['sector_groups'] or i['region_group'] == 'Other':
            print(f'  note: #{i["rank"]} {i["name"]} filed under "Other" (sector "{i["sector"]}", region "{i["region"]}")')
    data = dict(title=f'IdeaMille Top {len(ideas)}', ranked_date=ranked, ranked_label=f'Ranked {label[1]}', count=len(ideas),
                fields=['rank', 'name', 'sector', 'region', 'stage', 'description', 'url', 'origin', 'origin_label', 'sector_groups', 'region_group'],
                ideas=ideas)
    out = {ROOT / 'data' / 'top-ideas.json': json.dumps(data, indent=1, ensure_ascii=False) + '\n',
           ROOT / 'html' / 'top-ideas.html': splice(ROOT / 'html' / 'top-ideas.html', 'IM-TOP100', render_list(ideas, label)),
           ROOT / 'html' / 'ideabase.html': splice(ROOT / 'html' / 'ideabase.html', 'IM-TOP10', render_top10(ideas, label)),
           ROOT / 'index.html': splice(ROOT / 'index.html', 'IM-TOP-CALLOUT', render_callout(ideas, label))}
    private = [h for h in header if h not in PUBLIC]           # never shipped; prove it
    for p, txt in out.items():
        hit = [h for h in private if h.lower() in txt.lower()]
        if hit: die(f'{p.relative_to(ROOT)} would contain a non-public column name; stopped.')
    if a.check_links: check_links(ideas)
    if a.dry_run: print(f'dry run OK: {len(ideas)} ideas, ranked {ranked}; nothing written.'); return
    for p, txt in out.items(): p.write_text(txt, encoding='utf-8')
    sm = ROOT / 'sitemap.xml'
    if sm.exists():
        s = re.sub(r'(<loc>https://ideamille\.com/(?:|html/(?:top-ideas|ideabase)\.html)</loc><lastmod>)[^<]*', r'\g<1>' + ranked, sm.read_text())
        sm.write_text(s)
    print(f'wrote {len(ideas)} ideas ranked {ranked} ({label[1]}) to data/top-ideas.json, html/top-ideas.html, html/ideabase.html (top 10), index.html')
    print('Review the pages locally, then commit and push only with Michael\'s OK.')

if __name__ == '__main__':
    main()
