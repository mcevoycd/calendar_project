(function () {
  const SNAPSHOT_DB_NAME = 'fluid-notes-offline-db';
  const SNAPSHOT_DB_VERSION = 1;
  const SNAPSHOT_STORE_NAME = 'snapshots';
  const SNAPSHOT_SECTIONS = ['diary', 'todo', 'notes'];
  const QUEUE_DB_NAME = 'fluid-notes-offline-sync-db';
  const QUEUE_DB_VERSION = 1;
  const QUEUE_STORE_NAME = 'formQueue';
  const LAST_SYNC_KEY = 'fluid-notes-offline-last-sync';
  const DEBUG_FLAG_KEY = 'fluid-notes-offline-debug';
  const DEBUG_QUERY_KEY = 'debug-offline';
  const LONG_PRESS_MS = 800;
  const REFRESH_INTERVAL_MS = 15000;
  let panelNode = null;
  let panelBackdropNode = null;
  let panelBodyNode = null;
  let refreshTimer = 0;
  let latestStatus = null;

  function canUseLocalStorage() {
    try {
      return Boolean(window.localStorage);
    } catch (error) {
      return false;
    }
  }

  function readDebugFlag() {
    if (!canUseLocalStorage()) {
      return false;
    }
    return window.localStorage.getItem(DEBUG_FLAG_KEY) === '1';
  }

  function writeDebugFlag(enabled) {
    if (!canUseLocalStorage()) {
      return;
    }
    window.localStorage.setItem(DEBUG_FLAG_KEY, enabled ? '1' : '0');
  }

  function applyQueryDebugFlag() {
    const params = new URLSearchParams(window.location.search || '');
    if (!params.has(DEBUG_QUERY_KEY)) {
      return;
    }

    const rawValue = String(params.get(DEBUG_QUERY_KEY) || '').trim().toLowerCase();
    writeDebugFlag(rawValue === '1' || rawValue === 'true' || rawValue === 'yes');
  }

  function readLastSyncAt() {
    if (!canUseLocalStorage()) {
      return '';
    }
    return window.localStorage.getItem(LAST_SYNC_KEY) || '';
  }

  function formatIso(isoValue, fallbackLabel) {
    if (!isoValue) {
      return fallbackLabel || 'Not available';
    }

    const parsed = new Date(isoValue);
    if (Number.isNaN(parsed.getTime())) {
      return fallbackLabel || 'Not available';
    }

    return parsed.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatStorageBytes(byteCount) {
    if (!Number.isFinite(byteCount) || byteCount < 0) {
      return 'Unknown';
    }

    const units = ['B', 'KB', 'MB', 'GB'];
    let value = byteCount;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }

    const digits = value >= 100 || unitIndex === 0 ? 0 : 1;
    return value.toFixed(digits) + ' ' + units[unitIndex];
  }

  function openIndexedDb(dbName, version, upgradeHandler) {
    return new Promise(function (resolve, reject) {
      if (!('indexedDB' in window)) {
        reject(new Error('indexedDB unavailable'));
        return;
      }

      const request = indexedDB.open(dbName, version);
      request.onupgradeneeded = function (event) {
        if (typeof upgradeHandler === 'function') {
          upgradeHandler(event.target.result);
        }
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error || new Error('indexedDB open failed'));
      };
    });
  }

  function readAllSnapshots() {
    return openIndexedDb(SNAPSHOT_DB_NAME, SNAPSHOT_DB_VERSION, function (db) {
      if (!db.objectStoreNames.contains(SNAPSHOT_STORE_NAME)) {
        const store = db.createObjectStore(SNAPSHOT_STORE_NAME, { keyPath: 'section' });
        store.createIndex('updatedAt', 'updatedAt', { unique: false });
      }
    }).then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(SNAPSHOT_STORE_NAME, 'readonly');
        const store = tx.objectStore(SNAPSHOT_STORE_NAME);
        const request = store.getAll();
        request.onsuccess = function () {
          resolve(Array.isArray(request.result) ? request.result : []);
        };
        request.onerror = function () {
          reject(request.error || new Error('snapshot read failed'));
        };
        tx.oncomplete = function () {
          db.close();
        };
      });
    }).catch(function () {
      return [];
    });
  }

  function readQueueEntries() {
    return openIndexedDb(QUEUE_DB_NAME, QUEUE_DB_VERSION, function (db) {
      if (!db.objectStoreNames.contains(QUEUE_STORE_NAME)) {
        db.createObjectStore(QUEUE_STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    }).then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(QUEUE_STORE_NAME, 'readonly');
        const store = tx.objectStore(QUEUE_STORE_NAME);
        const request = store.getAll();
        request.onsuccess = function () {
          resolve(Array.isArray(request.result) ? request.result : []);
        };
        request.onerror = function () {
          reject(request.error || new Error('queue read failed'));
        };
        tx.oncomplete = function () {
          db.close();
        };
      });
    }).catch(function () {
      return [];
    });
  }

  function getDisplayModeLabel() {
    const standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
    return standalone ? 'Standalone app' : 'Browser tab';
  }

  function getCurrentSection() {
    const path = window.location.pathname || '';
    if (path.indexOf('/diary') === 0) {
      return 'diary';
    }
    if (path.indexOf('/todo') === 0) {
      return 'todo';
    }
    if (path.indexOf('/notes') === 0) {
      return 'notes';
    }
    return 'other';
  }

  async function readCacheStatus() {
    if (!('caches' in window)) {
      return { available: false, names: [], fallbackCached: false };
    }

    try {
      const names = await window.caches.keys();
      const fallback = await window.caches.match('/static/dashboard/offline.html');
      return {
        available: true,
        names: names,
        fallbackCached: Boolean(fallback)
      };
    } catch (error) {
      return { available: false, names: [], fallbackCached: false };
    }
  }

  async function readServiceWorkerStatus() {
    if (!('serviceWorker' in navigator)) {
      return {
        supported: false,
        registered: false,
        controlled: false,
        state: 'unsupported'
      };
    }

    try {
      const registration = await navigator.serviceWorker.getRegistration('/');
      const activeWorker = registration && (registration.active || registration.waiting || registration.installing);
      return {
        supported: true,
        registered: Boolean(registration),
        controlled: Boolean(navigator.serviceWorker.controller),
        state: activeWorker && activeWorker.state ? activeWorker.state : (registration ? 'registered' : 'missing')
      };
    } catch (error) {
      return {
        supported: true,
        registered: false,
        controlled: Boolean(navigator.serviceWorker.controller),
        state: 'error'
      };
    }
  }

  async function readStorageEstimate() {
    if (!navigator.storage || typeof navigator.storage.estimate !== 'function') {
      return { supported: false };
    }

    try {
      const estimate = await navigator.storage.estimate();
      return {
        supported: true,
        usage: Number(estimate.usage || 0),
        quota: Number(estimate.quota || 0)
      };
    } catch (error) {
      return { supported: false };
    }
  }

  function computeReadiness(status) {
    const snapshotCount = status.snapshots.presentCount;
    const hasAllSnapshots = snapshotCount === SNAPSHOT_SECTIONS.length;
    const hasSetup = status.serviceWorker.registered || status.serviceWorker.controlled || snapshotCount > 0 || status.cache.fallbackCached;
    const hasConflicts = status.queue.conflictCount > 0;

    if (status.serviceWorker.controlled && status.cache.fallbackCached && hasAllSnapshots && !hasConflicts) {
      return {
        tone: 'ready',
        label: 'Offline ready',
        detail: status.queue.pendingCount ? (status.queue.pendingCount + ' queued change' + (status.queue.pendingCount === 1 ? '' : 's')) : 'All core sections cached'
      };
    }

    if (hasSetup) {
      let detail = 'Open Diary, To Do, and Notes online once';
      if (hasConflicts) {
        detail = status.queue.conflictCount + ' sync conflict' + (status.queue.conflictCount === 1 ? '' : 's');
      } else if (!hasAllSnapshots) {
        detail = snapshotCount + '/' + SNAPSHOT_SECTIONS.length + ' sections cached';
      } else if (!status.serviceWorker.controlled) {
        detail = 'Reload once to activate offline cache';
      }

      return {
        tone: 'partial',
        label: 'Offline partial',
        detail: detail
      };
    }

    return {
      tone: 'missing',
      label: 'Offline setup needed',
      detail: 'Visit the main sections while online'
    };
  }

  async function collectStatus() {
    const snapshotRows = await readAllSnapshots();
    const snapshotMap = {};
    snapshotRows.forEach(function (row) {
      if (row && row.section) {
        snapshotMap[row.section] = row;
      }
    });

    const queueRows = await readQueueEntries();
    const serviceWorker = await readServiceWorkerStatus();
    const cache = await readCacheStatus();
    const storage = await readStorageEstimate();
    const lastSyncAt = readLastSyncAt();
    const snapshots = {
      sections: SNAPSHOT_SECTIONS.map(function (section) {
        const row = snapshotMap[section] || null;
        return {
          section: section,
          present: Boolean(row && row.payload),
          updatedAt: row && row.updatedAt ? row.updatedAt : ''
        };
      })
    };
    snapshots.presentCount = snapshots.sections.filter(function (entry) {
      return entry.present;
    }).length;

    const queue = {
      pendingCount: queueRows.length,
      conflictCount: queueRows.filter(function (entry) {
        return Boolean(entry && entry.blocked);
      }).length
    };

    const status = {
      generatedAt: new Date().toISOString(),
      currentSection: getCurrentSection(),
      online: navigator.onLine,
      displayMode: getDisplayModeLabel(),
      serviceWorker: serviceWorker,
      cache: cache,
      snapshots: snapshots,
      queue: queue,
      lastSyncAt: lastSyncAt,
      storage: storage
    };

    status.readiness = computeReadiness(status);
    return status;
  }

  function ensureStyles() {
    if (document.getElementById('offline-diagnostics-styles')) {
      return;
    }

    const style = document.createElement('style');
    style.id = 'offline-diagnostics-styles';
    style.textContent = [
      '.offline-diagnostics-backdrop{position:fixed;inset:0;z-index:99996;background:rgba(2,10,18,.58);display:none;}',
      '.offline-diagnostics-panel{position:fixed;right:.8rem;top:calc(env(safe-area-inset-top) + 4.5rem);z-index:99997;display:none;width:min(92vw,420px);max-height:min(78vh,620px);overflow:hidden;border-radius:18px;border:1px solid rgba(53,136,183,.42);background:rgba(7,25,40,.98);box-shadow:0 24px 54px rgba(0,0,0,.42);color:#eaf4ff;font:600 .76rem/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}',
      '.offline-diagnostics-panel header{display:flex;align-items:flex-start;justify-content:space-between;gap:.8rem;padding:.9rem .95rem .7rem;border-bottom:1px solid rgba(143,166,185,.18);}',
      '.offline-diagnostics-panel h2{margin:0;font-size:.9rem;}',
      '.offline-diagnostics-panel p{margin:.18rem 0 0;color:#9fb7cb;font-size:.72rem;font-weight:500;}',
      '.offline-diagnostics-body{display:grid;gap:.75rem;padding:.85rem .95rem .95rem;overflow:auto;max-height:min(68vh,540px);}',
      '.offline-diagnostics-group{display:grid;gap:.42rem;padding:.72rem .76rem;border-radius:14px;border:1px solid rgba(53,136,183,.24);background:rgba(9,27,42,.84);}',
      '.offline-diagnostics-group h3{margin:0;font-size:.78rem;color:#dceafa;letter-spacing:.01em;}',
      '.offline-diagnostics-list{display:grid;gap:.34rem;margin:0;padding:0;list-style:none;}',
      '.offline-diagnostics-item{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem;}',
      '.offline-diagnostics-item strong{font-size:.72rem;color:#dceafa;}',
      '.offline-diagnostics-item span{font-size:.72rem;color:#9fb7cb;text-align:right;}',
      '.offline-diagnostics-pill{display:inline-flex;align-items:center;justify-content:center;padding:.12rem .45rem;border-radius:999px;border:1px solid rgba(53,136,183,.36);font-size:.64rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;}',
      '.offline-diagnostics-pill[data-tone="ready"]{border-color:rgba(74,222,128,.42);background:rgba(8,43,30,.92);color:#d5f7de;}',
      '.offline-diagnostics-pill[data-tone="partial"]{border-color:rgba(250,204,21,.46);background:rgba(55,43,13,.94);color:#fff0bf;}',
      '.offline-diagnostics-pill[data-tone="missing"]{border-color:rgba(248,113,113,.42);background:rgba(60,19,24,.94);color:#ffd6d6;}',
      '.offline-diagnostics-actions{display:flex;flex-wrap:wrap;gap:.5rem;}',
      '.offline-diagnostics-actions button{border:1px solid rgba(53,136,183,.46);border-radius:10px;background:rgba(11,39,59,.96);color:#dceafa;font:700 .72rem/1.2 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:.42rem .62rem;}',
      '.offline-diagnostics-actions button[data-danger="1"]{border-color:rgba(248,113,113,.42);background:rgba(60,19,24,.94);color:#ffd6d6;}',
      '@media (max-width: 640px){.offline-diagnostics-panel{left:.8rem;right:.8rem;top:auto;bottom:calc(env(safe-area-inset-bottom) + 1rem);width:auto;max-height:min(72vh,620px);}}'
    ].join('');
    document.head.appendChild(style);
  }

  function closePanel() {
    if (panelNode) {
      panelNode.style.display = 'none';
    }
    if (panelBackdropNode) {
      panelBackdropNode.style.display = 'none';
    }
  }

  function createPanel() {
    if (panelNode && panelBackdropNode && panelBodyNode) {
      return;
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'offline-diagnostics-backdrop';
    backdrop.addEventListener('click', closePanel);

    const panel = document.createElement('aside');
    panel.className = 'offline-diagnostics-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'Offline diagnostics');

    const header = document.createElement('header');
    const headingWrap = document.createElement('div');
    const heading = document.createElement('h2');
    heading.textContent = 'Offline Diagnostics';
    const subtitle = document.createElement('p');
    subtitle.textContent = 'Open this from Settings whenever you need offline diagnostics.';
    headingWrap.appendChild(heading);
    headingWrap.appendChild(subtitle);

    const controls = document.createElement('div');
    controls.className = 'offline-diagnostics-actions';

    const refreshBtn = document.createElement('button');
    refreshBtn.type = 'button';
    refreshBtn.textContent = 'Refresh';
    refreshBtn.addEventListener('click', function () {
      refreshStatus();
    });

    const disableBtn = document.createElement('button');
    disableBtn.type = 'button';
    disableBtn.textContent = 'Hide debug';
    disableBtn.setAttribute('data-danger', '1');
    disableBtn.addEventListener('click', function () {
      writeDebugFlag(false);
      closePanel();
      renderStatus(latestStatus);
    });

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = 'Close';
    closeBtn.addEventListener('click', closePanel);

    controls.appendChild(refreshBtn);
    controls.appendChild(disableBtn);
    controls.appendChild(closeBtn);
    header.appendChild(headingWrap);
    header.appendChild(controls);

    const body = document.createElement('div');
    body.className = 'offline-diagnostics-body';

    panel.appendChild(header);
    panel.appendChild(body);
    document.body.appendChild(backdrop);
    document.body.appendChild(panel);

    panelBackdropNode = backdrop;
    panelNode = panel;
    panelBodyNode = body;

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closePanel();
      }
    });
  }

  function appendKeyValueList(container, items) {
    const list = document.createElement('ul');
    list.className = 'offline-diagnostics-list';
    items.forEach(function (item) {
      const row = document.createElement('li');
      row.className = 'offline-diagnostics-item';
      const key = document.createElement('strong');
      key.textContent = item.label;
      const value = document.createElement('span');
      value.textContent = item.value;
      row.appendChild(key);
      row.appendChild(value);
      list.appendChild(row);
    });
    container.appendChild(list);
  }

  function buildGroup(titleText) {
    const section = document.createElement('section');
    section.className = 'offline-diagnostics-group';
    const title = document.createElement('h3');
    title.textContent = titleText;
    section.appendChild(title);
    return section;
  }

  function renderPanel(status) {
    if (!readDebugFlag()) {
      closePanel();
      return;
    }

    createPanel();
    panelBodyNode.innerHTML = '';

    const readinessGroup = buildGroup('Readiness');
    const readinessPill = document.createElement('span');
    readinessPill.className = 'offline-diagnostics-pill';
    readinessPill.setAttribute('data-tone', status.readiness.tone);
    readinessPill.textContent = status.readiness.label;
    readinessGroup.appendChild(readinessPill);
    appendKeyValueList(readinessGroup, [
      { label: 'Current section', value: status.currentSection },
      { label: 'Device network', value: status.online ? 'Online' : 'Offline' },
      { label: 'Display mode', value: status.displayMode },
      { label: 'Last queue sync', value: formatIso(status.lastSyncAt, 'Not synced yet') },
      { label: 'Updated', value: formatIso(status.generatedAt, 'Just now') }
    ]);

    const swGroup = buildGroup('Service Worker');
    appendKeyValueList(swGroup, [
      { label: 'Supported', value: status.serviceWorker.supported ? 'Yes' : 'No' },
      { label: 'Registered', value: status.serviceWorker.registered ? 'Yes' : 'No' },
      { label: 'Controlling page', value: status.serviceWorker.controlled ? 'Yes' : 'No' },
      { label: 'Worker state', value: status.serviceWorker.state }
    ]);

    const cacheGroup = buildGroup('Cached App Shell');
    appendKeyValueList(cacheGroup, [
      { label: 'Cache API available', value: status.cache.available ? 'Yes' : 'No' },
      { label: 'Offline fallback cached', value: status.cache.fallbackCached ? 'Yes' : 'No' },
      { label: 'Cache buckets', value: status.cache.names.length ? String(status.cache.names.length) : '0' }
    ]);

    const snapshotGroup = buildGroup('Local Snapshots');
    appendKeyValueList(snapshotGroup, status.snapshots.sections.map(function (entry) {
      return {
        label: entry.section,
        value: entry.present ? ('Saved ' + formatIso(entry.updatedAt, 'Unknown')) : 'Missing'
      };
    }));

    const queueGroup = buildGroup('Offline Queue');
    appendKeyValueList(queueGroup, [
      { label: 'Pending actions', value: String(status.queue.pendingCount) },
      { label: 'Conflicts', value: String(status.queue.conflictCount) },
      { label: 'Queue health', value: status.queue.conflictCount ? 'Needs review' : 'Ready' }
    ]);

    const storageGroup = buildGroup('Browser Storage');
    const usageText = status.storage.supported
      ? (formatStorageBytes(status.storage.usage) + ' of ' + formatStorageBytes(status.storage.quota))
      : 'Unavailable';
    appendKeyValueList(storageGroup, [
      { label: 'Storage estimate', value: usageText },
      { label: 'Debug mode', value: readDebugFlag() ? 'Enabled' : 'Disabled' }
    ]);

    panelBodyNode.appendChild(readinessGroup);
    panelBodyNode.appendChild(swGroup);
    panelBodyNode.appendChild(cacheGroup);
    panelBodyNode.appendChild(snapshotGroup);
    panelBodyNode.appendChild(queueGroup);
    panelBodyNode.appendChild(storageGroup);
  }

  function renderStatus(status) {
    latestStatus = status;
    renderPanel(status);
  }

  function openPanel() {
    if (!readDebugFlag() || !latestStatus) {
      return;
    }
    createPanel();
    renderPanel(latestStatus);
    panelBackdropNode.style.display = 'block';
    panelNode.style.display = 'block';
  }

  function refreshStatus() {
    collectStatus().then(renderStatus).catch(function () {
      renderStatus({
        readiness: {
          tone: 'missing',
          label: 'Offline setup needed',
          detail: 'Diagnostics unavailable'
        },
        currentSection: getCurrentSection(),
        online: navigator.onLine,
        displayMode: getDisplayModeLabel(),
        serviceWorker: { supported: 'serviceWorker' in navigator, registered: false, controlled: Boolean(navigator.serviceWorker && navigator.serviceWorker.controller), state: 'error' },
        cache: { available: 'caches' in window, names: [], fallbackCached: false },
        snapshots: { sections: SNAPSHOT_SECTIONS.map(function (section) { return { section: section, present: false, updatedAt: '' }; }), presentCount: 0 },
        queue: { pendingCount: 0, conflictCount: 0 },
        lastSyncAt: readLastSyncAt(),
        storage: { supported: false },
        generatedAt: new Date().toISOString()
      });
    });
  }

  function attachListeners() {
    window.addEventListener('online', refreshStatus);
    window.addEventListener('offline', refreshStatus);
    window.addEventListener('pageshow', refreshStatus);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) {
        refreshStatus();
      }
    });

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('controllerchange', refreshStatus);
    }

    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(function () {
      if (!document.hidden) {
        refreshStatus();
      }
    }, REFRESH_INTERVAL_MS);
  }

  function init() {
    ensureStyles();
    applyQueryDebugFlag();
    attachListeners();
    refreshStatus();
    window.FluidNotesOfflineDiagnostics = {
      refreshStatus: refreshStatus,
      openPanel: openPanel
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();