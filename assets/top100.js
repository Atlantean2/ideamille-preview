/* IdeaMille Top 100: search and filters for the pre-rendered list (static; no data fetch needed). */
(function () {
  var form = document.getElementById('t100-tools'), list = document.getElementById('t100-list');
  if (!form || !list || !document.querySelectorAll) return;
  var items = Array.prototype.slice.call(list.querySelectorAll('li.im-t100-item'));
  var q = document.getElementById('t100-q'), fs = document.getElementById('t100-sector'),
      fr = document.getElementById('t100-region'), fo = document.getElementById('t100-origin'),
      count = document.getElementById('t100-count'), empty = document.getElementById('t100-empty');
  function norm(s) { s = (s || '').toLowerCase(); return s.normalize ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '') : s; }
  var text = items.map(function (li) { return norm(li.textContent.replace(/ \(opens in a new tab\)/g, '')); });
  function apply() {
    var words = norm(q.value).split(/\s+/).filter(Boolean), s = fs.value, r = fr.value, o = fo.value, shown = 0;
    items.forEach(function (li, k) {
      var ok = (!s || (' ' + li.getAttribute('data-sg') + ' ').indexOf(' ' + s + ' ') > -1) &&
               (!r || li.getAttribute('data-rg') === r) && (!o || li.getAttribute('data-origin') === o) &&
               words.every(function (w) { return text[k].indexOf(w) > -1; });
      li.hidden = !ok; if (ok) shown++;
    });
    var all = !words.length && !s && !r && !o;
    count.textContent = all ? 'Showing all ' + items.length : 'Showing ' + shown + ' of ' + items.length;
    empty.hidden = shown > 0;
  }
  function reset() { q.value = ''; fs.value = ''; fr.value = ''; fo.value = ''; apply(); q.focus(); }
  [q, fs, fr, fo].forEach(function (el) { el.addEventListener(el === q ? 'input' : 'change', apply); });
  document.getElementById('t100-reset').addEventListener('click', reset);
  document.getElementById('t100-reset2').addEventListener('click', reset);
  form.hidden = false;
  apply();
})();
