#!/usr/bin/env python3
"""Refresh data/ideas.json from the IdeaMille ideas Google Sheet.

Usage:  python3 tools/refresh_ideas.py "<published CSV URL of the Sheet>"
   or:  python3 tools/refresh_ideas.py ideas.csv
Expected columns (header row): id, name, cluster, stage, summary, featured, public, rank
Only rows with public = TRUE/yes/1 are shown on the site. Nothing is published until you
commit and push the updated data/ideas.json (needs Michael's OK).
"""
import csv, io, json, sys, datetime, urllib.request, pathlib
src = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
raw = urllib.request.urlopen(src).read().decode('utf-8') if src.startswith('http') else open(src, encoding='utf-8').read()
truthy = lambda v: str(v).strip().lower() in ('1', 'true', 'yes', 'y', 'x')
ideas = []
for i, r in enumerate(csv.DictReader(io.StringIO(raw))):
    if not (r.get('name') or '').strip():
        continue
    ideas.append(dict(id=(r.get('id') or f'idea-{i+1:03d}').strip(), name=r['name'].strip(),
                      cluster=(r.get('cluster') or '').strip(), stage=(r.get('stage') or '').strip(),
                      summary=(r.get('summary') or '').strip(), featured=truthy(r.get('featured', '')),
                      public=truthy(r.get('public', 'yes')), rank=int(r['rank']) if (r.get('rank') or '').strip().isdigit() else i + 1))
ideas.sort(key=lambda x: x['rank'])
out = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'ideas.json'
json.dump(dict(source='IdeaMille ideas Google Sheet', updated=datetime.date.today().isoformat(), ideas=ideas), open(out, 'w'), indent=1)
print(f'wrote {len(ideas)} ideas to {out}')
