// app.js - Renders data.js content into the page
function render() {
  const container = document.getElementById('content');
  const navLinks = document.getElementById('navLinks');
  if (!window.CNS_DATA) { container.innerHTML = '<p style="color:red;text-align:center">data.js not loaded!</p>'; return; }
  
  let html = '';
  let navHtml = '';
  const units = window.CNS_DATA;

  units.forEach((unit, ui) => {
    const uid = 'unit' + (ui + 1);
    navHtml += `<li><a href="#${uid}">${unit.short || unit.title}</a></li>`;
    
    html += `<section class="unit-section" id="${uid}">`;
    html += `<div class="unit-header u${ui+1}">`;
    html += `<span class="unit-number">${String(ui+1).padStart(2,'0')}</span>`;
    html += `<h2>${unit.title}</h2>`;
    if (unit.badge) html += `<span class="badge badge-${unit.badge}">${unit.badge.toUpperCase()}</span>`;
    html += `</div>`;

    unit.questions.forEach((q, qi) => {
      const marksClass = q.marks <= 2 ? 'marks-2' : q.marks <= 4 ? 'marks-4' : 'marks-6';
      html += `<div class="q-card" data-search="${(q.q + ' ' + (q.hindi||'') + ' ' + q.answer).toLowerCase()}">`;
      html += `<div class="q-card-header" onclick="toggleCard(this)">`;
      html += `<div class="q-icon ${marksClass}">${q.marks}M</div>`;
      html += `<div class="q-text">${q.q}${q.hindi ? '<span class="hindi">'+q.hindi+'</span>' : ''}</div>`;
      html += `<span class="q-toggle">▼</span>`;
      html += `</div>`;
      html += `<div class="q-card-body"><div class="q-answer"><h4>Answer</h4>${q.answer}</div></div>`;
      html += `</div>`;
    });
    html += `</section>`;
  });

  container.innerHTML = html;
  navLinks.innerHTML = navHtml;
  updateProgress();
}

function toggleCard(header) {
  const card = header.closest('.q-card');
  card.classList.toggle('open');
  updateProgress();
}

let allOpen = false;
function toggleAll() {
  allOpen = !allOpen;
  document.querySelectorAll('.q-card').forEach(c => {
    if (allOpen) c.classList.add('open');
    else c.classList.remove('open');
  });
  updateProgress();
}

function updateProgress() {
  const total = document.querySelectorAll('.q-card').length;
  const opened = document.querySelectorAll('.q-card.open').length;
  const pct = total ? Math.round((opened / total) * 100) : 0;
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressText').textContent = `${opened} / ${total} topics read`;
}

// Search
document.getElementById('searchBox').addEventListener('input', function() {
  const val = this.value.toLowerCase().trim();
  document.querySelectorAll('.q-card').forEach(card => {
    const text = card.getAttribute('data-search') || '';
    card.style.display = val === '' || text.includes(val) ? '' : 'none';
  });
  document.querySelectorAll('.unit-section').forEach(sec => {
    const visible = sec.querySelectorAll('.q-card[style=""], .q-card:not([style])').length;
    sec.style.display = val === '' || visible > 0 ? '' : 'none';
  });
});

document.addEventListener('DOMContentLoaded', render);
