(function () {
  const SNAPSHOT_IDS = {
    diary: 'offline-diary-data',
    todo: 'offline-todo-data',
    notes: 'offline-notes-data'
  };

  const DB_NAME = 'fluid-notes-offline-db';
  const DB_VERSION = 1;
  const STORE_NAME = 'snapshots';

  function getSectionKey() {
    const path = window.location.pathname || '';
    if (path.startsWith('/diary')) {
      return 'diary';
    }
    if (path.startsWith('/todo')) {
      return 'todo';
    }
    if (path.startsWith('/notes')) {
      return 'notes';
    }
    return '';
  }

  function parseInlineSnapshot(sectionKey) {
    const scriptId = SNAPSHOT_IDS[sectionKey];
    if (!scriptId) {
      return null;
    }

    const node = document.getElementById(scriptId);
    if (!node) {
      return null;
    }

    try {
      return JSON.parse(node.textContent || '{}');
    } catch (error) {
      console.warn('Fluid Notes offline snapshot parse failed.', error);
      return null;
    }
  }

  function openOfflineDb() {
    return new Promise(function (resolve, reject) {
      if (!('indexedDB' in window)) {
        reject(new Error('indexedDB unavailable'));
        return;
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = function (event) {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'section' });
          store.createIndex('updatedAt', 'updatedAt', { unique: false });
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

  function putSnapshot(record) {
    return openOfflineDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        store.put(record);
        transaction.oncomplete = function () {
          resolve();
        };
        transaction.onerror = function () {
          reject(transaction.error || new Error('snapshot write failed'));
        };
      }).finally(function () {
        db.close();
      });
    });
  }

  function saveCurrentPageSnapshot() {
    const section = getSectionKey();
    if (!section) {
      return;
    }

    const payload = parseInlineSnapshot(section);
    if (!payload) {
      return;
    }

    const record = {
      section: section,
      path: window.location.pathname,
      updatedAt: new Date().toISOString(),
      payload: payload
    };

    putSnapshot(record).catch(function (error) {
      console.warn('Fluid Notes offline snapshot save failed.', error);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', saveCurrentPageSnapshot, { once: true });
  } else {
    saveCurrentPageSnapshot();
  }
})();
