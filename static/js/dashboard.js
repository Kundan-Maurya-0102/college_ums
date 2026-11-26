/* Student dashboard shell: mobile drawer, dropdowns, dark mode, skeletons.
   No framework, no CDN. Everything degrades to plain links if JS is off. */
(function () {
  'use strict';

  var body = document.body;
  var sidebar = document.getElementById('dash-sidebar');
  var toggle = document.getElementById('nav-toggle');
  var scrim = document.getElementById('dash-scrim');

  /* ── mobile drawer ─────────────────────────────────────────────── */
  function closeDrawer() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    if (scrim) scrim.hidden = true;
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function openDrawer() {
    if (!sidebar) return;
    sidebar.classList.add('is-open');
    if (scrim) scrim.hidden = false;
    if (toggle) toggle.setAttribute('aria-expanded', 'true');
    var first = sidebar.querySelector('a');
    if (first) first.focus();
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      if (sidebar && sidebar.classList.contains('is-open')) closeDrawer();
      else openDrawer();
    });
  }
  if (scrim) scrim.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      closeDrawer();
      closeMenus(null);
    }
  });
  // Tapping a sidebar link on a phone moves to a new page; close first so the
  // drawer does not stay open while the page swaps.
  if (sidebar) {
    sidebar.addEventListener('click', function (event) {
      if (event.target.closest('a') && window.matchMedia('(max-width: 900px)').matches) {
        closeDrawer();
      }
    });
  }

  /* ── navbar dropdowns: only one open, click outside closes ──────── */
  var menus = Array.prototype.slice.call(document.querySelectorAll('.dash-menu'));

  function closeMenus(except) {
    menus.forEach(function (menu) {
      if (menu !== except) menu.removeAttribute('open');
    });
  }

  menus.forEach(function (menu) {
    menu.addEventListener('toggle', function () {
      if (menu.open) closeMenus(menu);
    });
    // Keyboard: Escape inside a panel closes it and returns focus to the summary.
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        menu.removeAttribute('open');
        var summary = menu.querySelector('summary');
        if (summary) summary.focus();
      }
    });
  });

  document.addEventListener('click', function (event) {
    if (!event.target.closest('.dash-menu')) closeMenus(null);
  });

  /* ── dark mode: same colour variables, remembered per browser ───── */
  var THEME_KEY = 'ums.dash.theme';
  var themeButton = document.getElementById('dash-theme');

  function applyTheme(mode) {
    var dark = mode === 'dark';
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    if (themeButton) themeButton.setAttribute('aria-pressed', dark ? 'true' : 'false');
    try { localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light'); } catch (e) { /* private mode */ }
    // Server-side hint for the next full page load (no flash of light theme).
    document.cookie = 'ums_theme=' + (dark ? 'dark' : 'light') + ';path=/;max-age=31536000;samesite=Lax';
  }

  var saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) { saved = null; }
  if (saved) applyTheme(saved);

  if (themeButton) {
    themeButton.addEventListener('click', function () {
      applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
  }

  /* ── skeletons: hide the grid placeholder once the page is interactive ── */
  body.classList.remove('dash-loading');
  var skeleton = document.querySelector('.dash-skeleton');
  if (skeleton) skeleton.hidden = true;
})();

/* ── in-page subject filter (the navbar search icon focuses it) ─────── */
(function () {
  'use strict';
  var input = document.getElementById('course-filter');
  var list = document.querySelector('.dash-courses');
  if (!input || !list) return;

  var empty = document.getElementById('course-filter-empty');
  var rows = Array.prototype.slice.call(list.querySelectorAll('.dash-course'));

  function apply() {
    var needle = input.value.trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (row) {
      var hit = !needle || row.textContent.toLowerCase().indexOf(needle) !== -1;
      row.hidden = !hit;
      if (hit) shown += 1;
    });
    if (empty) empty.hidden = shown !== 0;
    list.hidden = shown === 0;
  }

  input.addEventListener('input', apply);
})();

/* Dismissible alert banner: remembered per banner text, not forever. */
(function () {
  var banner = document.getElementById('dash-banner');
  var close = document.getElementById('dash-banner-close');
  if (!banner || !close) return;

  var key = 'ums.dash.banner.' + (banner.getAttribute('data-banner-key') || 'x');
  try {
    if (window.localStorage.getItem(key) === '1') {
      banner.hidden = true;
      return;
    }
  } catch (err) { /* private mode: banner simply stays visible */ }

  close.addEventListener('click', function () {
    banner.hidden = true;
    try { window.localStorage.setItem(key, '1'); } catch (err) { /* ignore */ }
  });
})();

/* One open menu at a time; Escape and outside clicks close them. */
(function () {
  var menus = Array.prototype.slice.call(document.querySelectorAll('.dash-menu'));

  function closeAll(except) {
    menus.forEach(function (menu) {
      if (menu !== except) menu.open = false;
    });
  }

  menus.forEach(function (menu) {
    menu.addEventListener('toggle', function () {
      if (menu.open) closeAll(menu);
    });
  });

  document.addEventListener('click', function (event) {
    if (!event.target.closest('.dash-menu')) closeAll(null);
    var contact = event.target.closest('.dash-quick-contact details');
    document.querySelectorAll('.dash-quick-contact details[open]').forEach(function (node) {
      if (node !== contact) node.open = false;
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    closeAll(null);
    document.querySelectorAll('.dash-quick-contact details[open]').forEach(function (node) {
      node.open = false;
    });
  });

  /* "/" jumps to the navbar search, like most dashboards. */
  var search = document.getElementById('dash-q');
  if (search) {
    document.addEventListener('keydown', function (event) {
      if (event.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
        event.preventDefault();
        search.focus();
      }
    });
  }
})();
