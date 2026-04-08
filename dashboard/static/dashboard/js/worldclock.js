// static/dashboard/js/worldclock.js
console.log('worldclock.js loaded');

const TZ_FLAGS = {
  'Europe/London': 'UK',
  'America/New_York': 'US',
  'Asia/Tokyo': 'JP',
  'Europe/Paris': 'FR',
  'Europe/Berlin': 'DE',
  'America/Los_Angeles': 'US',
  'Australia/Sydney': 'AU',
  'Asia/Singapore': 'SG',
  'America/Chicago': 'US',
  'America/Denver': 'US',
  'America/Anchorage': 'US',
  'America/Mexico_City': 'MX',
  'America/Sao_Paulo': 'BR',
  'Asia/Dubai': 'AE',
  'Asia/Hong_Kong': 'HK',
  'America/Toronto': 'CA',
  'Europe/Madrid': 'ES',
  'Asia/Manila': 'PH',
  'UTC': 'UTC'
};

const TZ_DISPLAY_NAMES = {
  'America/Chicago': 'Texas'
};

const CITY_TO_TZ = {
  'london': 'Europe/London',
  'new york': 'America/New_York',
  'nyc': 'America/New_York',
  'tokyo': 'Asia/Tokyo',
  'paris': 'Europe/Paris',
  'berlin': 'Europe/Berlin',
  'los angeles': 'America/Los_Angeles',
  'la': 'America/Los_Angeles',
  'sydney': 'Australia/Sydney',
  'singapore': 'Asia/Singapore',
  'chicago': 'America/Chicago',
  'denver': 'America/Denver',
  'anchorage': 'America/Anchorage',
  'mexico city': 'America/Mexico_City',
  'sao paulo': 'America/Sao_Paulo',
  'dubai': 'Asia/Dubai',
  'hong kong': 'Asia/Hong_Kong',
  'toronto': 'America/Toronto',
  'madrid': 'Europe/Madrid',
  'dallas': 'America/Chicago',
  'texas': 'America/Chicago',
  'manila': 'Asia/Manila',
  'manilla': 'Asia/Manila',
  'utc': 'UTC'
};

function formatClock(timeZone, hour12) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12
  }).format(new Date());
}

function parseDateParts(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).formatToParts(date);
  const result = {};
  parts.forEach(part => {
    if (part.type !== 'literal') {
      result[part.type] = part.value;
    }
  });
  return result;
}

function formatOffset(timeZone) {
  try {
    const date = new Date();
    const zoneParts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    }).formatToParts(date);
    const zoneNamePart = zoneParts.find(part => part.type === 'timeZoneName');
    const abbreviation = zoneNamePart ? zoneNamePart.value : '';

    const localParts = parseDateParts(date, timeZone);
    const utcParts = parseDateParts(date, 'UTC');
    const localTimestamp = Date.UTC(
      Number(localParts.year),
      Number(localParts.month) - 1,
      Number(localParts.day),
      Number(localParts.hour),
      Number(localParts.minute),
      Number(localParts.second)
    );
    const utcTimestamp = Date.UTC(
      Number(utcParts.year),
      Number(utcParts.month) - 1,
      Number(utcParts.day),
      Number(utcParts.hour),
      Number(utcParts.minute),
      Number(utcParts.second)
    );
    const offsetMinutes = (localTimestamp - utcTimestamp) / 60000;
    const offsetHours = Math.round(offsetMinutes / 60);
    const sign = offsetHours >= 0 ? '+' : '-';
    const gmtLabel = `GMT${sign}${Math.abs(offsetHours)}`;
    return abbreviation ? `${abbreviation} (${gmtLabel})` : `(${gmtLabel})`;
  } catch (error) {
    return '';
  }
}

function getSortValue(timeZone) {
  const parts = parseDateParts(new Date(), timeZone);
  return Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second)
  );
}

function getFlag(timeZone) {
  return TZ_FLAGS[timeZone] || '🌍';
}

function getTimezoneLabel(timeZone) {
  if (TZ_DISPLAY_NAMES[timeZone]) {
    return TZ_DISPLAY_NAMES[timeZone];
  }
  return timeZone.split('/').pop().replace(/_/g, ' ');
}

function isValidTimezone(value) {
  try {
    Intl.DateTimeFormat(undefined, { timeZone: value });
    return true;
  } catch (error) {
    return false;
  }
}

function normalizeText(value) {
  return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

function resolveTimezone(value) {
  if (!value) return null;
  const trimmed = value.trim();
  if (trimmed.includes('/')) {
    const maybeTz = trimmed.split('/').map(part => part.trim()).join('/');
    if (isValidTimezone(maybeTz)) {
      return maybeTz;
    }
  }

  const normalized = normalizeText(trimmed);
  if (CITY_TO_TZ[normalized]) {
    return CITY_TO_TZ[normalized];
  }

  const found = Object.keys(TZ_FLAGS).find(tz => tz.toLowerCase().endsWith('/' + normalized));
  if (found) {
    return found;
  }

  return null;
}

function renderWorldClock() {
  const container = document.getElementById('worldclock-container');
  const toggle = document.getElementById('toggle-time-format');
  const addButton = document.getElementById('add-timezone');
  const timezoneInput = document.getElementById('timezone-input');
  const popupModal = document.getElementById('app-popup-modal');
  const popupTitle = document.getElementById('app-popup-title');
  const popupMessage = document.getElementById('app-popup-message');
  const popupCancelBtn = document.getElementById('app-popup-cancel-btn');
  const popupOkBtn = document.getElementById('app-popup-ok-btn');
  console.log('renderWorldClock init', { container, toggle, addButton, timezoneInput });
  if (!container) {
    console.error('World clock container not found');
    return;
  }
  if (!toggle) {
    console.warn('World clock toggle button not found');
  }
  if (!addButton) {
    console.warn('World clock add button not found');
  }
  if (!timezoneInput) {
    console.warn('World clock timezone input not found');
  }

  const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  let hour12 = localStorage.getItem('worldclockHour12') !== 'false';
  let timezones = JSON.parse(container.getAttribute('data-timezones') || '[]');

  function showPopup(message, options) {
    const config = options || {};
    const title = config.title || 'Notice';
    const mode = config.mode || 'alert';
    const okText = config.okText || 'OK';
    const cancelText = config.cancelText || 'Cancel';

    if (!popupModal || !popupMessage || !popupOkBtn || !popupCancelBtn || !popupTitle) {
      console.warn('World clock popup modal elements are missing. Message:', message);
      return Promise.resolve(mode !== 'confirm');
    }

    popupTitle.textContent = title;
    popupMessage.textContent = message;
    popupOkBtn.textContent = okText;
    popupCancelBtn.textContent = cancelText;
    popupCancelBtn.hidden = mode !== 'confirm';
    popupModal.hidden = false;
    popupOkBtn.focus();

    return new Promise(function (resolve) {
      let settled = false;

      function close(result) {
        if (settled) {
          return;
        }
        settled = true;
        popupModal.hidden = true;
        popupModal.removeEventListener('click', onBackdropClick);
        document.removeEventListener('keydown', onKeyDown);
        popupCancelBtn.removeEventListener('click', onCancel);
        popupOkBtn.removeEventListener('click', onOk);
        resolve(result);
      }

      function onOk() {
        close(true);
      }

      function onCancel() {
        close(false);
      }

      function onBackdropClick(event) {
        if (event.target === popupModal) {
          close(false);
        }
      }

      function onKeyDown(event) {
        if (event.key === 'Escape') {
          close(false);
        }
      }

      popupModal.addEventListener('click', onBackdropClick);
      document.addEventListener('keydown', onKeyDown);
      popupCancelBtn.addEventListener('click', onCancel);
      popupOkBtn.addEventListener('click', onOk);
    });
  }

  function saveTimezones() {
    container.setAttribute('data-timezones', JSON.stringify(timezones));
  }

  function updateToggleText() {
    toggle.textContent = hour12 ? 'AM/PM' : '24-hour';
    toggle.classList.toggle('btn-outline-primary', !hour12);
    toggle.classList.toggle('btn-primary', hour12);
  }

  function buildItems() {
    container.innerHTML = '';
    const sortedTimezones = [...timezones].sort((a, b) => getSortValue(a) - getSortValue(b));

    sortedTimezones.forEach(tz => {
      const card = document.createElement('div');
      card.className = 'clock-item';
      if (tz === localTimezone) {
        card.classList.add('highlight');
      }

      const zone = document.createElement('div');
      zone.className = 'clock-zone';
      zone.textContent = getTimezoneLabel(tz);
      card.dataset.tz = tz;

      const time = document.createElement('div');
      time.className = 'clock-time';
      time.textContent = formatClock(tz, hour12);

      const info = document.createElement('div');
      info.className = 'clock-subtitle';
      info.textContent = formatOffset(tz) + (tz === localTimezone ? ' · Local timezone' : '');

      const actions = document.createElement('div');
      actions.style.display = 'flex';
      actions.style.justifyContent = 'flex-end';

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'btn btn-sm btn-outline-secondary';
      removeButton.textContent = 'Remove';
      removeButton.addEventListener('click', function () {
        timezones = timezones.filter(existing => existing !== tz);
        saveTimezones();
        buildItems();
      });

      actions.appendChild(removeButton);
      card.appendChild(zone);
      card.appendChild(time);
      card.appendChild(info);
      card.appendChild(actions);
      container.appendChild(card);
    });
  }

  function tick() {
    container.querySelectorAll('.clock-item').forEach(card => {
      const tz = card.dataset.tz;
      const timeEl = card.querySelector('.clock-time');
      if (!tz || !timeEl) return;
      timeEl.textContent = formatClock(tz, hour12);
    });
  }

  toggle.addEventListener('click', function () {
    hour12 = !hour12;
    localStorage.setItem('worldclockHour12', String(hour12));
    updateToggleText();
    buildItems();
  });

  function addTimezone(value) {
    const resolved = resolveTimezone(value);
    if (!resolved) {
      showPopup('Invalid city or timezone. Enter a city like Paris or a valid IANA timezone.', {
        title: 'World Clock'
      });
      return;
    }
    if (timezones.includes(resolved)) {
      showPopup('This timezone is already in your list.', {
        title: 'World Clock'
      });
      return;
    }
    if (timezones.length >= 3) {
      showPopup('Maximum of 3 clocks allowed. Remove one before adding another.', {
        title: 'World Clock'
      });
      return;
    }
    timezones.push(resolved);
    saveTimezones();
    buildItems();
    if (timezoneInput) {
      timezoneInput.value = '';
      timezoneInput.focus();
    }
  }

  if (addButton) {
    addButton.addEventListener('click', function () {
      if (!timezoneInput) return;
      if (!timezoneInput.value.trim()) return;
      addTimezone(timezoneInput.value);
    });
  }

  if (timezoneInput) {
    timezoneInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        addTimezone(timezoneInput.value);
      }
    });
  }

  updateToggleText();
  buildItems();
  tick();
  setInterval(tick, 1000);
}

document.addEventListener('DOMContentLoaded', renderWorldClock);
