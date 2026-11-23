/* College UMS — shared UI behaviour (no dependencies).
   - mobile sidebar drawer (+ backdrop, ESC, scroll lock)
   - light/dark theme toggle, persisted in localStorage
   - form submit lock (prevents double submits)
   - toast auto-dismiss
   - data-confirm links/buttons
*/
(function () {
  "use strict";

  /* ── sidebar drawer ─────────────────────────────────────────────── */
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("sidebar-backdrop");
  var toggle = document.getElementById("sidebar-toggle");

  function setDrawer(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    if (backdrop) backdrop.classList.toggle("show", open);
    document.body.style.overflow = open ? "hidden" : "";
    if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      setDrawer(!sidebar.classList.contains("open"));
    });
  }
  if (backdrop) backdrop.addEventListener("click", function () { setDrawer(false); });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setDrawer(false);
  });
  sidebar && sidebar.addEventListener("click", function (e) {
    if (e.target.closest("a") && window.innerWidth <= 1024) setDrawer(false);
  });

  /* ── theme toggle ───────────────────────────────────────────────── */
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem("ums-theme"); } catch (err) { stored = null; }
  if (stored) root.setAttribute("data-theme", stored);

  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("ums-theme", next); } catch (err) {}
      themeBtn.setAttribute("aria-label", next === "dark" ? "Light mode" : "Dark mode");
    });
  }

  /* ── submit lock ────────────────────────────────────────────────── */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || form.dataset.noLock === "true") return;
    if (form.checkValidity && !form.checkValidity()) return;
    var btn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.dataset.originalText = btn.value || btn.textContent;
    var label = "Please wait…";
    if (btn.tagName === "INPUT") btn.value = label; else btn.textContent = label;
    // re-enable if the browser restores the page from cache
    setTimeout(function () {
      if (!btn.dataset.originalText) return;
      btn.disabled = false;
      if (btn.tagName === "INPUT") btn.value = btn.dataset.originalText;
      else btn.textContent = btn.dataset.originalText;
    }, 8000);
  });

  /* ── confirms ───────────────────────────────────────────────────── */
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-confirm]");
    if (!el) return;
    if (!window.confirm(el.getAttribute("data-confirm"))) {
      e.preventDefault();
      e.stopPropagation();
    }
  });

  /* ── toasts ─────────────────────────────────────────────────────── */
  var stack = document.getElementById("toast-stack");
  if (stack) {
    Array.prototype.forEach.call(stack.querySelectorAll(".alert"), function (alertEl) {
      var close = alertEl.querySelector(".alert-close");
      function remove() { alertEl.remove(); }
      if (close) close.addEventListener("click", remove);
      if (!alertEl.classList.contains("alert-error")) setTimeout(remove, 6000);
    });
  }
})();
