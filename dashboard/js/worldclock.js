// static/dashboard/js/worldclock.js
function formatTime(date) {
  return date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function renderWorldClock() {
  const container = document.getElementById('worldclock');
  if (!container) return;

  const timezones = JSON.parse(container.getAttribute('data-timezones') || '[]');
  container.innerHTML = '';

  timezones.forEach(tz => {
    const div = document.createElement('div');
    div.className = 'clock-item';
    div.dataset.tz = tz;
    container.appendChild(div);
  });

  function tick() {
    const now = new Date();
    container.querySelectorAll('.clock-item').forEach(el => {
      const tz = el.dataset.tz;
      const time = now.toLocaleString('en-GB', {
        timeZone: tz,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
      el.textContent = `${tz}: ${time}`;
    });
  }

  tick();
  setInterval(tick, 1000);
}

document.addEventListener('DOMContentLoaded', renderWorldClock);
