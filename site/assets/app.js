(function () {
  var PREFS = 'reader:prefs';
  var root = document.documentElement;

  // 1) 套用字級／行距偏好
  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem(PREFS)) || {}; } catch (e) { return {}; }
  }
  function applyPrefs(p) {
    if (p.fs) root.style.setProperty('--fs', p.fs + 'px');
    if (p.lh) root.style.setProperty('--lh', String(p.lh));
  }
  var prefs = loadPrefs();
  applyPrefs(prefs);

  function savePrefs() { try { localStorage.setItem(PREFS, JSON.stringify(prefs)); } catch (e) {} }
  function nudge(kind, dir) {
    if (kind === 'fs') prefs.fs = Math.min(28, Math.max(15, (prefs.fs || 20) + dir));
    else prefs.lh = Math.min(2.4, Math.max(1.4, Math.round(((prefs.lh || 1.9) + dir * 0.1) * 10) / 10));
    applyPrefs(prefs); savePrefs();
  }
  var toggle = document.getElementById('prefs-toggle');
  var panel = document.getElementById('prefs-panel');
  if (toggle && panel) {
    toggle.addEventListener('click', function () { panel.hidden = !panel.hidden; });
    panel.addEventListener('click', function (e) {
      var t = e.target;
      if (t.dataset.fs) nudge('fs', Number(t.dataset.fs));
      if (t.dataset.lh) nudge('lh', Number(t.dataset.lh));
    });
  }

  var slug = document.body.getAttribute('data-slug');
  var chapter = document.body.getAttribute('data-chapter');
  var KEY = slug ? 'reader:progress:' + slug : null;

  // 2) 章頁：還原捲動、記錄進度（捲動百分比）
  if (KEY && chapter) {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
    if (saved && saved.chapter === chapter && saved.percent > 0) {
      requestAnimationFrame(function () {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        window.scrollTo(0, h * saved.percent);
      });
    }
    var t = null;
    function record() {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      var percent = h > 0 ? Math.min(1, window.scrollY / h) : 0;
      try { localStorage.setItem(KEY, JSON.stringify({ chapter: chapter, percent: percent })); } catch (e) {}
    }
    window.addEventListener('scroll', function () {
      if (t) return; t = setTimeout(function () { t = null; record(); }, 400);
    }, { passive: true });
    window.addEventListener('pagehide', record);
  }

  // 3) 目錄頁：顯示「繼續閱讀」
  if (KEY && !chapter) {
    var el = document.getElementById('continue');
    var p = null;
    try { p = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
    if (el && p && p.chapter) {
      el.textContent = '繼續閱讀 ' + p.chapter;
      el.href = p.chapter + '.html';
      el.hidden = false;
    }
  }
})();
