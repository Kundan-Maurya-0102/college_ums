/* Progressive table tools: search, sort, CSV export, mobile card labels.
   Works on any <table class="data-table"> that is already rendered by Django;
   no server changes and no extra requests. */
(function () {
  "use strict";

  var MIN_ROWS_FOR_TOOLS = 4;

  function rowCells(row) {
    return Array.prototype.slice.call(row.children);
  }

  function cellText(cell) {
    var sortValue = cell.getAttribute("data-sort");
    if (sortValue !== null) return sortValue;
    return (cell.textContent || "").replace(/\s+/g, " ").trim();
  }

  function compare(a, b) {
    var numA = parseFloat(a.replace(/[^0-9.\-]/g, ""));
    var numB = parseFloat(b.replace(/[^0-9.\-]/g, ""));
    var numeric = a !== "" && b !== "" && !isNaN(numA) && !isNaN(numB)
      && /^[^a-zA-Z]*$/.test(a) && /^[^a-zA-Z]*$/.test(b);
    if (numeric) return numA - numB;
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
  }

  function csvCell(value) {
    var text = value.replace(/"/g, '""');
    return /[",\n;]/.test(text) ? '"' + text + '"' : text;
  }

  function downloadCsv(table, name) {
    var lines = [];
    var headers = Array.prototype.map.call(table.tHead ? table.tHead.rows[0].cells : [], cellText);
    lines.push(headers.map(csvCell).join(","));
    Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
      if (row.classList.contains("is-hidden") || row.dataset.emptyRow === "1") return;
      lines.push(rowCells(row).map(function (cell) { return csvCell(cellText(cell)); }).join(","));
    });
    if (lines.length < 2) return;

    var blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = (name || "table") + "-" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function labelCells(table) {
    var headRow = table.tHead && table.tHead.rows[0];
    if (!headRow) return;
    var labels = Array.prototype.map.call(headRow.cells, function (th) {
      return (th.textContent || "").replace(/\s+/g, " ").trim() || "—";
    });
    Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
      rowCells(row).forEach(function (cell, index) {
        if (!cell.hasAttribute("data-label") && labels[index]) {
          cell.setAttribute("data-label", labels[index]);
        }
      });
    });
  }

  function setupSort(table, headRow) {
    var current = { index: -1, dir: 1 };
    Array.prototype.forEach.call(headRow.cells, function (th, index) {
      if (th.dataset.nosort !== undefined) return;
      th.classList.add("is-sortable");
      th.setAttribute("tabindex", "0");
      th.setAttribute("role", "button");
      th.setAttribute("aria-sort", "none");

      function sortBy() {
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows).filter(function (row) {
          return row.dataset.emptyRow !== "1";
        });
        var dir = current.index === index ? -current.dir : 1;
        current = { index: index, dir: dir };
        rows.sort(function (a, b) {
          return compare(cellText(a.cells[index]), cellText(b.cells[index])) * dir;
        });
        rows.forEach(function (row) { body.appendChild(row); });
        Array.prototype.forEach.call(headRow.cells, function (other) {
          other.setAttribute("aria-sort", "none");
        });
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
      }

      th.addEventListener("click", sortBy);
      th.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          sortBy();
        }
      });
    });
  }

  function enhance(table) {
    if (table.dataset.tableEnhanced === "1" || !table.tBodies.length) return;
    var body = table.tBodies[0];
    var rows = Array.prototype.slice.call(body.rows).filter(function (row) {
      if (row.classList.contains("empty-row") || row.dataset.emptyRow === "1") return false;
      // "No records found" rows are a single colspan cell.
      return !(row.cells.length === 1 && row.cells[0].hasAttribute("colspan"));
    });
    if (rows.length < MIN_ROWS_FOR_TOOLS) return;

    table.dataset.tableEnhanced = "1";
    labelCells(table);
    var headRow = table.tHead && table.tHead.rows[0];
    if (headRow) setupSort(table, headRow);

    var host = table.closest(".table-responsive") || table;
    var toolbar = document.createElement("div");
    toolbar.className = "table-toolbar";
    toolbar.innerHTML =
      '<div class="table-search-wrap">' +
        '<svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16"><path d="M10 4a6 6 0 1 0 3.5 10.9l4.3 4.3 1.4-1.4-4.3-4.3A6 6 0 0 0 10 4zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8z"/></svg>' +
        '<input type="search" class="table-search" placeholder="Search this table…" aria-label="Search this table">' +
      "</div>" +
      '<span class="table-count" aria-live="polite"></span>' +
      '<button type="button" class="btn btn-sm btn-secondary table-export">Export CSV</button>';

    host.parentNode.insertBefore(toolbar, host);

    var input = toolbar.querySelector(".table-search");
    var count = toolbar.querySelector(".table-count");
    var total = rows.length;

    function updateCount(visible) {
      count.textContent = (total - visible) > 0
        ? visible + " of " + total + " rows"
        : total + (total === 1 ? " row" : " rows");
    }
    updateCount(total);

    input.addEventListener("input", function () {
      var term = input.value.toLowerCase().trim();
      var visible = 0;
      rows.forEach(function (row) {
        var match = !term || (row.textContent || "").toLowerCase().indexOf(term) !== -1;
        row.classList.toggle("is-hidden", !match);
        if (match) visible += 1;
      });
      updateCount(visible);
      var noMatch = table.querySelector(".table-no-match");
      if (!noMatch) {
        noMatch = document.createElement("tr");
        noMatch.className = "table-no-match";
        noMatch.innerHTML = '<td colspan="' + (headRow ? headRow.cells.length : 1) + '">' +
          '<div class="empty-state"><p>No rows match “<span></span>”.</p></div></td>';
        body.appendChild(noMatch);
      }
      noMatch.hidden = visible !== 0;
      var label = noMatch.querySelector("span");
      if (label) label.textContent = input.value;
    });

    toolbar.querySelector(".table-export").addEventListener("click", function () {
      var heading = document.querySelector("h1, .page-title");
      downloadCsv(table, (heading ? heading.textContent : "export").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
    });
  }

  function init(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("table.data-table"), enhance);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(); });
  } else {
    init();
  }
  document.addEventListener("ui:content-updated", function () { init(); });
})();
