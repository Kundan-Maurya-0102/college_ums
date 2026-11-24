/* First-login tour: one short, role-aware walk-through per browser.
 * Shown once (localStorage), restartable from Help → "Replay the welcome tour",
 * dismissible with Escape / "Skip", and never blocks a form submit.
 * No dependencies; all text comes from data attributes in the page. */
(function () {
  'use strict';

  var STORAGE_KEY = 'ums.tour.seen';
  var root = document.querySelector('[data-tour-steps]');
  if (!root) return;

  var steps = [];
  try { steps = JSON.parse(root.getAttribute('data-tour-steps')) || []; } catch (e) { steps = []; }
  if (!steps.length) return;

  var lang = document.documentElement.lang || 'en';
  var ui = {
    en: { next: 'Next', back: 'Back', done: 'Got it', skip: 'Skip tour', step: 'Step' },
    hi: { next: 'आगे', back: 'पीछे', done: 'समझ गया', skip: 'टूर छोड़ें', step: 'चरण' }
  }[lang] || { next: 'Next', back: 'Back', done: 'Got it', skip: 'Skip tour', step: 'Step' };

  var index = 0;
  var backdrop = null;

  function seen() {
    try { return localStorage.getItem(STORAGE_KEY) === '1'; } catch (e) { return true; }
  }
  function markSeen() {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) { /* private mode */ }
  }

  function dot(i) {
    return '<span class="tour-step-dot' + (i === index ? ' is-active' : '') + '"></span>';
  }

  function render() {
    var step = steps[index];
    var dots = '';
    for (var i = 0; i < steps.length; i++) dots += dot(i);
    var isLast = index === steps.length - 1;

    backdrop = document.createElement('div');
    backdrop.className = 'tour-backdrop';
    backdrop.setAttribute('role', 'dialog');
    backdrop.setAttribute('aria-modal', 'true');
    backdrop.setAttribute('aria-labelledby', 'tour-title');
    backdrop.innerHTML =
      '<div class="tour-card">' +
        '<div class="tour-steps" aria-hidden="true">' + dots + '</div>' +
        '<h2 id="tour-title">' + step.title + '</h2>' +
        '<p>' + step.body + '</p>' +
        '<div class="tour-actions">' +
          '<button type="button" class="btn btn-outline" data-tour-skip>' + ui.skip + '</button>' +
          '<span style="display:flex;gap:8px;">' +
            (index > 0 ? '<button type="button" class="btn btn-outline" data-tour-back>' + ui.back + '</button>' : '') +
            '<button type="button" class="btn btn-primary" data-tour-next>' + (isLast ? ui.done : ui.next) + '</button>' +
          '</span>' +
        '</div>' +
      '</div>';

    backdrop.addEventListener('click', function (event) {
      var target = event.target.closest('[data-tour-next],[data-tour-back],[data-tour-skip]');
      if (!target) return;
      if (target.hasAttribute('data-tour-skip')) return finish();
      if (target.hasAttribute('data-tour-back')) { index = Math.max(0, index - 1); return rerender(); }
      if (index === steps.length - 1) return finish();
      index += 1;
      rerender();
    });

    document.body.appendChild(backdrop);
    var primary = backdrop.querySelector('[data-tour-next]');
    if (primary) primary.focus();
  }

  function rerender() {
    if (backdrop) backdrop.remove();
    render();
  }

  function finish() {
    if (backdrop) backdrop.remove();
    backdrop = null;
    markSeen();
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && backdrop) finish();
  });

  document.querySelectorAll('[data-tour-restart]').forEach(function (button) {
    button.addEventListener('click', function () {
      index = 0;
      rerender();
    });
  });

  if (!seen()) {
    // let the page settle first so the tour is not fighting a layout shift
    window.setTimeout(render, 600);
  }
})();
