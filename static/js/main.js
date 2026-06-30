/* Smart Quiz System — Main JS v5 Improved */

// Auto-dismiss flash alerts
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  }, 5000);
});

// Mobile nav toggle
(function() {
  const toggle = document.getElementById('nav-toggle');
  const links  = document.getElementById('nav-links');
  if (!toggle || !links) return;
  toggle.addEventListener('click', () => links.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (!toggle.contains(e.target) && !links.contains(e.target)) {
      links.classList.remove('open');
    }
  });
})();

// Quiz logic — handled inline in quiz.html template

// Auto-save indicator
function showSaveIndicator() {
  let el = document.getElementById('save-indicator');
  if (!el) {
    el = document.createElement('div');
    el.id = 'save-indicator';
    el.textContent = '✓ Saved';
    document.body.appendChild(el);
  }
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2000);
}

// Confirm delete buttons
document.querySelectorAll('.confirm-delete').forEach(btn => {
  btn.addEventListener('click', function(e) {
    if (!confirm('Are you sure? This cannot be undone.')) e.preventDefault();
  });
});

// Performance chart
(function initPerfChart() {
  const canvas = document.getElementById('perf-chart');
  if (!canvas || typeof Chart === 'undefined') return;
  const labels = JSON.parse(canvas.dataset.labels || '[]');
  const scores = JSON.parse(canvas.dataset.scores || '[]');
  const subjects = JSON.parse(canvas.dataset.subjects || '[]');
  new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Score %', data: scores,
        borderColor: '#c9a84c', backgroundColor: 'rgba(201,168,76,0.1)',
        borderWidth: 2.5, pointBackgroundColor: '#c9a84c',
        pointRadius: 5, tension: 0.35, fill: true
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => subjects[items[0].dataIndex] || labels[items[0].dataIndex],
            label: (item) => `Score: ${item.raw}%`
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8ba3bc' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { min: 0, max: 100, ticks: { color: '#8ba3bc', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.06)' } }
      }
    }
  });
})();

// Smooth scroll-to-top for long pages
(function() {
  const btn = document.createElement('button');
  btn.innerHTML = '↑';
  btn.style.cssText = 'position:fixed;bottom:1.5rem;left:1.5rem;width:36px;height:36px;border-radius:50%;background:var(--navy-light);border:1px solid var(--border);color:var(--text-muted);cursor:pointer;font-size:1rem;opacity:0;transition:opacity 0.3s;z-index:100;';
  document.body.appendChild(btn);
  window.addEventListener('scroll', () => {
    btn.style.opacity = window.scrollY > 400 ? '1' : '0';
  });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
})();
