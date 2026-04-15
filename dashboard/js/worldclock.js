// static/dashboard/js/worldclock.js
function formatTime(date) {
  return date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

function getOffsetMinutes(timeZone) {
  const now = new Date();
  const localText = now.toLocaleString('en-GB', {
    timeZone: timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
  const utcText = now.toLocaleString('en-GB', {
    timeZone: 'UTC',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
  return (new Date(localText).getTime() - new Date(utcText).getTime()) / 60000;
}

function renderWorldClock() {
  const container = document.getElementById('worldclock') || document.getElementById('worldclock-container');
  if (!container) return;

  const timezones = JSON.parse(container.getAttribute('data-timezones') || '[]')
    .sort(function (left, right) {
      const offsetDiff = getOffsetMinutes(left) - getOffsetMinutes(right);
      if (offsetDiff !== 0) {
        return offsetDiff;
      }
      return String(left || '').localeCompare(String(right || ''));
    });
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
        minute: '2-digit'
      });
      el.textContent = `${tz}: ${time}`;
    });
  }

  function scheduleNextTick() {
    const now = new Date();
    const delay = ((60 - now.getSeconds()) * 1000) - now.getMilliseconds();
    window.setTimeout(function () {
      tick();
      scheduleNextTick();
    }, Math.max(1000, delay));
  }

  tick();
  scheduleNextTick();
}

document.addEventListener('DOMContentLoaded', renderWorldClock);
