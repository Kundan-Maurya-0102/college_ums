/* Marks grid: spreadsheet habits for the teacher.
   - Tab / Shift+Tab / Enter / arrow keys move between cells
   - a value above the maximum is marked immediately and blocks saving
   - unsaved changes ask before leaving the page
   - a CSV (registration_number,marks) fills the grid without a round trip */
(function () {
  var form = document.getElementById('marks-form');
  if (!form) return;

  var max = parseInt(form.getAttribute('data-max-marks'), 10) || 0;
  var inputs = Array.prototype.slice.call(form.querySelectorAll('.marks-input'));
  var counter = form.querySelector('[data-grid-count]');
  var summary = form.querySelector('[data-grid-summary]');
  var save = form.querySelector('[data-save]');
  var dirty = false;

  function valueOf(input) {
    var raw = (input.value || '').trim();
    if (raw === '') return null;
    var n = Number(raw);
    return Number.isFinite(n) ? n : NaN;
  }

  function validate(input) {
    var value = valueOf(input);
    var row = input.closest('tr');
    var note = row ? row.querySelector('[data-row-error]') : null;
    var bad = false;
    var message = '';

    if (Number.isNaN(value)) {
      bad = true;
      message = 'Not a number';
    } else if (value !== null && (value < 0 || value > max)) {
      bad = true;
      message = 'Must be 0–' + max;
    }

    input.classList.toggle('is-invalid', bad);
    input.setAttribute('aria-invalid', bad ? 'true' : 'false');
    if (note) note.textContent = message;
    return !bad;
  }

  function refresh() {
    var filled = 0;
    var total = 0;
    var invalid = 0;
    inputs.forEach(function (input) {
      var value = valueOf(input);
      if (value !== null && !Number.isNaN(value)) { filled += 1; total += value; }
      if (!validate(input)) invalid += 1;
    });

    if (counter) {
      counter.textContent = filled + '/' + inputs.length + ' filled';
    }
    if (summary) {
      var avg = filled ? (total / filled).toFixed(1) : '—';
      summary.textContent = 'Average ' + avg + ' · empty rows are skipped';
    }
    if (save) {
      save.disabled = invalid > 0;
      save.setAttribute('aria-disabled', invalid ? 'true' : 'false');
    }
    return invalid === 0;
  }

  function markDirty() {
    dirty = true;
    document.body.classList.add('has-unsaved');
  }

  function focusAt(index) {
    var target = inputs[index];
    if (!target) return;
    target.focus();
    target.select();
    var row = target.closest('tr');
    if (row && row.scrollIntoView) row.scrollIntoView({ block: 'nearest' });
  }

  inputs.forEach(function (input, index) {
    input.addEventListener('input', function () { markDirty(); refresh(); });
    input.addEventListener('paste', function () { setTimeout(function () { markDirty(); refresh(); }, 0); });

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === 'ArrowDown') {
        event.preventDefault();
        focusAt(index + 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        focusAt(index - 1);
      } else if (event.key === 'Tab' && event.shiftKey) {
        /* let the browser handle Shift+Tab backwards */
      }
    });
  });

  /* CSV import: header may be present; "reg_no,marks" per line. */
  var csvInput = form.querySelector('[data-csv-input]');
  if (csvInput) {
    csvInput.addEventListener('change', function () {
      var file = csvInput.files && csvInput.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var lines = String(reader.result || '').split(/\r?\n/);
        var byReg = {};
        inputs.forEach(function (input) {
          var row = input.closest('tr');
          var reg = row ? row.children[1].textContent.trim() : '';
          if (reg) byReg[reg] = input;
        });
        var applied = 0;
        var skipped = 0;
        lines.forEach(function (line) {
          if (!line.trim()) return;
          var cells = line.split(',');
          var reg = (cells[0] || '').trim();
          var marks = (cells[1] || '').trim();
          if (!byReg[reg]) {
            if (!/reg/i.test(line)) skipped += 1;
            return;
          }
          if (marks === '') return;
          byReg[reg].value = marks;
          applied += 1;
        });
        markDirty();
        refresh();
        if (summary) {
          summary.textContent = 'CSV: ' + applied + ' row(s) filled' +
            (skipped ? ', ' + skipped + ' unmatched' : '');
        }
        csvInput.value = '';
      };
      reader.readAsText(file);
    });
  }

  form.addEventListener('submit', function (event) {
    if (!refresh()) {
      event.preventDefault();
      var firstBad = form.querySelector('.is-invalid');
      if (firstBad) firstBad.focus();
      return;
    }
    dirty = false;
  });

  window.addEventListener('beforeunload', function (event) {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });

  refresh();
})();
