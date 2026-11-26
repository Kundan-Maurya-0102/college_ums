/* Admin dashboard charts. Colours come from the CSS variables so dark mode and
   a college's PRIMARY_COLOR both apply without a second palette. */
(function () {
  var node = document.getElementById('chart-data');
  if (!node || typeof Chart === 'undefined') return;

  var data;
  try { data = JSON.parse(node.textContent); } catch (err) { return; }

  var styles = getComputedStyle(document.documentElement);
  var primary = styles.getPropertyValue('--primary').trim() || '#1d4ed8';
  var muted = styles.getPropertyValue('--muted').trim() || '#64748b';
  var line = styles.getPropertyValue('--line').trim() || '#e2e8f0';

  Chart.defaults.font.family = styles.getPropertyValue('--font-sans') || 'Inter, sans-serif';
  Chart.defaults.color = muted;

  function bar(id, series, label) {
    var canvas = document.getElementById(id);
    if (!canvas || !series.length) return;
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: series.map(function (row) { return row.label; }),
        datasets: [{ label: label, data: series.map(function (row) { return row.value; }),
                     backgroundColor: primary, borderRadius: 6, maxBarThickness: 42 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: line } } }
      }
    });
  }

  bar('chart-branches', data.branches, 'Students');
  bar('chart-fees', data.fees, 'Collected');

  var trendCanvas = document.getElementById('chart-trend');
  if (trendCanvas && data.trend.length) {
    new Chart(trendCanvas, {
      type: 'line',
      data: {
        labels: data.trend.map(function (row) { return row.label; }),
        datasets: [{
          label: 'Attendance %', data: data.trend.map(function (row) { return row.value; }),
          borderColor: primary, backgroundColor: primary, fill: false, tension: 0.3,
          pointRadius: 2
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, max: 100, grid: { color: line } }, x: { grid: { display: false } } }
      }
    });
  }
})();
