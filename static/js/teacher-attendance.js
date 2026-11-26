/* Attendance sheet: whole-class shortcuts, a live present/absent count and a
   guard against double submission. No framework, works without JS too (the
   checkboxes are ordinary form fields and start as "present"). */
(function () {
  var form = document.getElementById('attendance-form');
  if (!form) return;

  var boxes = Array.prototype.slice.call(form.querySelectorAll('.att-check'));
  var counters = document.querySelectorAll('[data-attendance-count]');
  var submit = form.querySelector('button[type="submit"]');

  function update() {
    var present = boxes.filter(function (box) { return box.checked; }).length;
    var absent = boxes.length - present;
    var text = present + ' present / ' + absent + ' absent';
    counters.forEach(function (node) { node.textContent = text; });
    if (submit) submit.textContent = 'Save attendance (' + present + ')';
  }

  function setAll(state) {
    boxes.forEach(function (box) { box.checked = state; });
    update();
  }

  document.querySelectorAll('[data-mark]').forEach(function (button) {
    button.addEventListener('click', function () {
      var mode = button.getAttribute('data-mark');
      if (mode === 'all-present') setAll(true);
      else if (mode === 'all-absent') setAll(false);
      else boxes.forEach(function (box) { box.checked = !box.checked; });
      update();
    });
  });

  boxes.forEach(function (box) { box.addEventListener('change', update); });

  form.addEventListener('submit', function (event) {
    if (form.getAttribute('data-submitting') === '1') {
      event.preventDefault();
      return;
    }
    form.setAttribute('data-submitting', '1');
    if (submit) {
      submit.disabled = true;
      submit.textContent = 'Saving…';
    }
  });

  update();
})();
