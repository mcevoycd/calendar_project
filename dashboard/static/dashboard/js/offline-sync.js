(function () {
  const DB_NAME = 'fluid-notes-offline-sync-db';
  const DB_VERSION = 1;
  const STORE_NAME = 'formQueue';
  const OFFLINE_PATH_PREFIXES = ['/diary', '/todo', '/notes'];
  const FILE_UPLOAD_WARNING = 'Offline queue does not support file uploads yet. Reconnect to upload attachments.';
  const LAST_SYNC_KEY = 'fluid-notes-offline-last-sync';
  const MAX_RETRY_ATTEMPTS = 3;
  const CONFLICT_HTTP_STATUSES = [404, 409, 412];
  let flushInProgress = false;
  let statusNode = null;
  let drawerBackdropNode = null;
  let drawerNode = null;
  let drawerListNode = null;
  let drawerMetaNode = null;

  function shouldHandleCurrentPath() {
    const path = window.location.pathname || '';
    return OFFLINE_PATH_PREFIXES.some(function (prefix) {
      return path === prefix || path.startsWith(prefix + '/');
    });
  }

  function createToastContainer() {
    let node = document.getElementById('offline-sync-toast-container');
    if (node) {
      return node;
    }

    node = document.createElement('div');
    node.id = 'offline-sync-toast-container';
    node.style.position = 'fixed';
    node.style.right = '0.8rem';
    node.style.bottom = '0.8rem';
    node.style.zIndex = '99999';
    node.style.display = 'grid';
    node.style.gap = '0.42rem';
    node.style.maxWidth = 'min(86vw, 360px)';
    document.body.appendChild(node);
    return node;
  }

  function showToast(message, isError) {
    if (!message) {
      return;
    }

    const container = createToastContainer();
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.padding = '0.62rem 0.72rem';
    toast.style.borderRadius = '10px';
    toast.style.fontSize = '0.82rem';
    toast.style.fontWeight = '600';
    toast.style.lineHeight = '1.35';
    toast.style.boxShadow = '0 12px 30px rgba(0,0,0,0.32)';
    toast.style.border = isError ? '1px solid rgba(251, 113, 133, 0.62)' : '1px solid rgba(52, 211, 153, 0.62)';
    toast.style.background = isError ? 'rgba(68, 16, 30, 0.96)' : 'rgba(8, 39, 35, 0.96)';
    toast.style.color = '#EAF4FF';

    container.appendChild(toast);

    window.setTimeout(function () {
      toast.remove();
    }, 4200);
  }

  function createStatusNode() {
    if (statusNode) {
      return statusNode;
    }

    const node = document.createElement('div');
    node.id = 'offline-sync-status';
    node.style.position = 'fixed';
    node.style.left = '0.8rem';
    node.style.bottom = '0.8rem';
    node.style.zIndex = '99998';
    node.style.padding = '0.5rem 0.62rem';
    node.style.borderRadius = '10px';
    node.style.background = 'rgba(7, 25, 40, 0.94)';
    node.style.border = '1px solid rgba(53, 136, 183, 0.5)';
    node.style.color = '#DCEBFA';
    node.style.fontSize = '0.75rem';
    node.style.fontWeight = '600';
    node.style.lineHeight = '1.35';
    node.style.boxShadow = '0 10px 24px rgba(0, 0, 0, 0.28)';
    node.style.maxWidth = 'min(84vw, 320px)';
    node.style.display = 'none';
    node.style.cursor = 'pointer';
    node.setAttribute('role', 'button');
    node.setAttribute('aria-label', 'Open offline queue details');
    node.setAttribute('tabindex', '0');
    node.addEventListener('click', function () {
      openQueueDrawer();
    });
    node.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openQueueDrawer();
      }
    });
    document.body.appendChild(node);
    statusNode = node;
    return statusNode;
  }

  function getPairValue(record, key) {
    if (!record || !Array.isArray(record.pairs)) {
      return '';
    }

    let found = '';
    record.pairs.forEach(function (pair) {
      if (pair[0] === key) {
        found = pair[1];
      }
    });
    return String(found || '').trim();
  }

  function getActionLabel(record) {
    const notesAction = getPairValue(record, 'notes_action');
    if (notesAction) {
      return 'Notes action: ' + notesAction;
    }

    const formType = getPairValue(record, 'form_type');
    if (formType) {
      return 'To Do action: ' + formType;
    }

    const actionUrl = String(record.actionUrl || '');
    if (actionUrl.indexOf('/diary/') !== -1) {
      return 'Diary action';
    }
    if (actionUrl.indexOf('/todo/') !== -1) {
      return 'To Do action';
    }
    if (actionUrl.indexOf('/notes/') !== -1) {
      return 'Notes action';
    }

    return 'Queued form action';
  }

  function getOperationKind(record) {
    const notesAction = getPairValue(record, 'notes_action');
    if (notesAction) {
      if (notesAction.indexOf('delete') === 0 || notesAction === 'clear_canvas') {
        return 'delete';
      }
      if (notesAction === 'new_canvas') {
        return 'replace';
      }
      return 'upsert';
    }

    const formType = getPairValue(record, 'form_type');
    if (formType) {
      if (formType.indexOf('delete') === 0 || formType.indexOf('clear') === 0) {
        return 'delete';
      }
      return 'upsert';
    }

    const actionUrl = String(record.actionUrl || '');
    if (actionUrl.indexOf('delete_') !== -1 || actionUrl.indexOf('/delete') !== -1) {
      return 'delete';
    }
    return 'upsert';
  }

  function getScopeKey(record) {
    try {
      const parsed = new URL(String(record.actionUrl || ''), window.location.origin);
      return parsed.pathname;
    } catch (error) {
      return String(record.pagePath || window.location.pathname || '/');
    }
  }

  function getResourceKey(record) {
    const taskId = getPairValue(record, 'task_id');
    if (taskId) {
      return 'todo-task:' + taskId;
    }

    const entryId = getPairValue(record, 'entry_id');
    if (entryId) {
      return 'diary-entry:' + entryId;
    }

    const noteId = getPairValue(record, 'note_id');
    if (noteId) {
      return 'note:' + noteId;
    }

    const categoryId = getPairValue(record, 'category_id');
    if (categoryId) {
      return 'note-category:' + categoryId;
    }

    const sectionKey = getPairValue(record, 'section_key');
    if (sectionKey) {
      return 'todo-section:' + sectionKey;
    }

    return getScopeKey(record) + ':' + getOperationKind(record);
  }

  function isConflictStatus(statusCode) {
    return CONFLICT_HTTP_STATUSES.indexOf(Number(statusCode || 0)) !== -1;
  }

  function getActionKind(record) {
    const notesAction = getPairValue(record, 'notes_action');
    if (notesAction) {
      return 'notes';
    }

    const formType = getPairValue(record, 'form_type');
    if (formType) {
      return 'todo';
    }

    const actionUrl = String(record.actionUrl || '');
    if (actionUrl.indexOf('/diary/') !== -1) {
      return 'diary';
    }
    if (actionUrl.indexOf('/todo/') !== -1) {
      return 'todo';
    }
    if (actionUrl.indexOf('/notes/') !== -1) {
      return 'notes';
    }

    return 'other';
  }

  function getActionBadgeTheme(kind) {
    if (kind === 'diary') {
      return {
        label: 'Diary',
        bg: 'rgba(56, 189, 248, 0.22)',
        border: 'rgba(56, 189, 248, 0.58)',
        color: '#D7F3FF'
      };
    }

    if (kind === 'todo') {
      return {
        label: 'To Do',
        bg: 'rgba(163, 230, 53, 0.2)',
        border: 'rgba(163, 230, 53, 0.56)',
        color: '#ECFAD0'
      };
    }

    if (kind === 'notes') {
      return {
        label: 'Notes',
        bg: 'rgba(250, 204, 21, 0.2)',
        border: 'rgba(250, 204, 21, 0.56)',
        color: '#FFF4C7'
      };
    }

    return {
      label: 'Other',
      bg: 'rgba(148, 163, 184, 0.18)',
      border: 'rgba(148, 163, 184, 0.52)',
      color: '#E2E8F0'
    };
  }

  function formatCreatedAt(isoValue) {
    if (!isoValue) {
      return 'Unknown time';
    }
    const parsed = new Date(isoValue);
    if (Number.isNaN(parsed.getTime())) {
      return 'Unknown time';
    }
    return parsed.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function createQueueDrawer() {
    if (drawerNode && drawerBackdropNode && drawerListNode && drawerMetaNode) {
      return;
    }

    const backdrop = document.createElement('div');
    backdrop.id = 'offline-sync-drawer-backdrop';
    backdrop.style.position = 'fixed';
    backdrop.style.inset = '0';
    backdrop.style.zIndex = '99996';
    backdrop.style.background = 'rgba(2, 10, 18, 0.55)';
    backdrop.style.display = 'none';
    backdrop.addEventListener('click', function () {
      closeQueueDrawer();
    });

    const drawer = document.createElement('aside');
    drawer.id = 'offline-sync-drawer';
    drawer.style.position = 'fixed';
    drawer.style.left = '0.8rem';
    drawer.style.bottom = '3.6rem';
    drawer.style.zIndex = '99997';
    drawer.style.width = 'min(92vw, 420px)';
    drawer.style.maxHeight = 'min(72vh, 520px)';
    drawer.style.display = 'none';
    drawer.style.flexDirection = 'column';
    drawer.style.gap = '0.62rem';
    drawer.style.padding = '0.72rem';
    drawer.style.borderRadius = '14px';
    drawer.style.background = 'rgba(7, 25, 40, 0.98)';
    drawer.style.border = '1px solid rgba(53, 136, 183, 0.58)';
    drawer.style.boxShadow = '0 20px 44px rgba(0, 0, 0, 0.42)';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', 'Offline queued actions');

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.justifyContent = 'space-between';
    header.style.gap = '0.5rem';

    const title = document.createElement('strong');
    title.textContent = 'Queued Offline Actions';
    title.style.color = '#EAF4FF';
    title.style.fontSize = '0.86rem';
    title.style.letterSpacing = '0.01em';

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = 'Close';
    closeBtn.style.border = '1px solid rgba(143, 166, 185, 0.48)';
    closeBtn.style.borderRadius = '8px';
    closeBtn.style.background = 'rgba(14, 27, 42, 0.95)';
    closeBtn.style.color = '#DCEBFA';
    closeBtn.style.fontSize = '0.74rem';
    closeBtn.style.fontWeight = '700';
    closeBtn.style.padding = '0.26rem 0.48rem';
    closeBtn.addEventListener('click', function () {
      closeQueueDrawer();
    });

    header.appendChild(title);
    header.appendChild(closeBtn);

    const meta = document.createElement('p');
    meta.style.margin = '0';
    meta.style.color = '#9FB7CB';
    meta.style.fontSize = '0.74rem';

    const list = document.createElement('ul');
    list.style.listStyle = 'none';
    list.style.margin = '0';
    list.style.padding = '0';
    list.style.display = 'grid';
    list.style.gap = '0.45rem';
    list.style.overflowY = 'auto';
    list.style.maxHeight = 'min(52vh, 360px)';

    const controls = document.createElement('div');
    controls.style.display = 'flex';
    controls.style.alignItems = 'center';
    controls.style.justifyContent = 'space-between';
    controls.style.gap = '0.6rem';

    const refreshBtn = document.createElement('button');
    refreshBtn.type = 'button';
    refreshBtn.textContent = 'Refresh';
    refreshBtn.style.border = '1px solid rgba(53, 136, 183, 0.55)';
    refreshBtn.style.borderRadius = '8px';
    refreshBtn.style.background = 'rgba(11, 39, 59, 0.95)';
    refreshBtn.style.color = '#DCEBFA';
    refreshBtn.style.fontSize = '0.74rem';
    refreshBtn.style.fontWeight = '700';
    refreshBtn.style.padding = '0.3rem 0.55rem';
    refreshBtn.addEventListener('click', function () {
      renderQueueDrawer();
    });

    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.textContent = 'Clear queue';
    clearBtn.style.border = '1px solid rgba(251, 113, 133, 0.55)';
    clearBtn.style.borderRadius = '8px';
    clearBtn.style.background = 'rgba(68, 16, 30, 0.9)';
    clearBtn.style.color = '#FFE1E8';
    clearBtn.style.fontSize = '0.74rem';
    clearBtn.style.fontWeight = '700';
    clearBtn.style.padding = '0.3rem 0.55rem';
    clearBtn.addEventListener('click', function () {
      clearQueue()
        .then(function () {
          showToast('Offline queue cleared.', false);
          renderQueueDrawer();
          updateQueueStatus();
        })
        .catch(function () {
          showToast('Unable to clear queue right now.', true);
        });
    });

    controls.appendChild(refreshBtn);
    controls.appendChild(clearBtn);

    drawer.appendChild(header);
    drawer.appendChild(meta);
    drawer.appendChild(list);
    drawer.appendChild(controls);

    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);

    drawerBackdropNode = backdrop;
    drawerNode = drawer;
    drawerListNode = list;
    drawerMetaNode = meta;

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeQueueDrawer();
      }
    });
  }

  function clearQueue() {
    return runTransaction('readwrite', function (store) {
      store.clear();
    });
  }

  function putQueuedAction(record) {
    return runTransaction('readwrite', function (store) {
      store.put(record);
    });
  }

  function coalesceQueue(record) {
    return getQueuedActions().then(function (items) {
      const sameResource = items.filter(function (item) {
        return item.id !== record.id && item.resourceKey === record.resourceKey && item.scopeKey === record.scopeKey;
      });

      if (!sameResource.length) {
        return;
      }

      const idsToDelete = sameResource.map(function (item) {
        return item.id;
      });

      return runTransaction('readwrite', function (store) {
        idsToDelete.forEach(function (id) {
          store.delete(id);
        });
      });
    });
  }

  function buildQueueRecord(actionUrl, pairs) {
    const record = {
      createdAt: new Date().toISOString(),
      pagePath: window.location.pathname,
      actionUrl: actionUrl,
      pairs: pairs,
      attempts: 0,
      blocked: false,
      conflict: false,
      lastError: '',
      operationKind: 'upsert',
      resourceKey: '',
      scopeKey: ''
    };

    record.operationKind = getOperationKind(record);
    record.scopeKey = getScopeKey(record);
    record.resourceKey = getResourceKey(record);
    return record;
  }

  function retryQueuedAction(entry) {
    const updated = Object.assign({}, entry, {
      attempts: 0,
      blocked: false,
      conflict: false,
      lastError: ''
    });

    return putQueuedAction(updated)
      .then(function () {
        return updateQueueStatus();
      })
      .then(function () {
        return renderQueueDrawer();
      })
      .then(function () {
        if (navigator.onLine) {
          return flushQueue();
        }
      });
  }

  function discardQueuedAction(entryId) {
    return deleteQueuedAction(entryId)
      .then(function () {
        return updateQueueStatus();
      })
      .then(function () {
        return renderQueueDrawer();
      });
  }

  function renderQueueDrawer() {
    createQueueDrawer();
    return getQueuedActions()
      .then(function (queued) {
        drawerListNode.innerHTML = '';

        if (!queued.length) {
          const empty = document.createElement('li');
          empty.textContent = 'No queued actions.';
          empty.style.padding = '0.55rem 0.62rem';
          empty.style.borderRadius = '10px';
          empty.style.border = '1px solid rgba(53, 136, 183, 0.26)';
          empty.style.background = 'rgba(9, 27, 42, 0.82)';
          empty.style.color = '#9FB7CB';
          empty.style.fontSize = '0.76rem';
          drawerListNode.appendChild(empty);
        } else {
          queued.forEach(function (entry) {
            const item = document.createElement('li');
            item.style.padding = '0.55rem 0.62rem';
            item.style.borderRadius = '10px';
            item.style.border = entry.blocked
              ? '1px solid rgba(251, 113, 133, 0.52)'
              : '1px solid rgba(53, 136, 183, 0.34)';
            item.style.background = 'rgba(9, 27, 42, 0.82)';
            item.style.display = 'grid';
            item.style.gap = '0.18rem';

            const head = document.createElement('div');
            head.style.display = 'flex';
            head.style.alignItems = 'center';
            head.style.justifyContent = 'space-between';
            head.style.gap = '0.5rem';

            const label = document.createElement('strong');
            label.textContent = getActionLabel(entry);
            label.style.color = '#EAF4FF';
            label.style.fontSize = '0.78rem';

            const badgeTheme = getActionBadgeTheme(getActionKind(entry));
            const badge = document.createElement('span');
            badge.textContent = badgeTheme.label;
            badge.style.display = 'inline-flex';
            badge.style.alignItems = 'center';
            badge.style.justifyContent = 'center';
            badge.style.padding = '0.1rem 0.45rem';
            badge.style.borderRadius = '999px';
            badge.style.background = badgeTheme.bg;
            badge.style.border = '1px solid ' + badgeTheme.border;
            badge.style.color = badgeTheme.color;
            badge.style.fontSize = '0.66rem';
            badge.style.fontWeight = '800';
            badge.style.letterSpacing = '0.03em';
            badge.style.textTransform = 'uppercase';

            const stamp = document.createElement('span');
            stamp.textContent = formatCreatedAt(entry.createdAt);
            stamp.style.color = '#9FB7CB';
            stamp.style.fontSize = '0.72rem';

            const state = document.createElement('span');
            state.style.fontSize = '0.7rem';
            if (entry.blocked) {
              state.textContent = 'Needs review: ' + (entry.lastError || 'conflict detected');
              state.style.color = '#FCA5A5';
            } else if (entry.attempts > 0) {
              state.textContent = 'Retry attempts: ' + entry.attempts;
              state.style.color = '#FCD34D';
            } else {
              state.textContent = 'Ready to sync';
              state.style.color = '#86EFAC';
            }

            const rowActions = document.createElement('div');
            rowActions.style.display = 'flex';
            rowActions.style.gap = '0.4rem';
            rowActions.style.marginTop = '0.1rem';

            if (entry.blocked) {
              const retryBtn = document.createElement('button');
              retryBtn.type = 'button';
              retryBtn.textContent = 'Retry';
              retryBtn.style.border = '1px solid rgba(53, 136, 183, 0.52)';
              retryBtn.style.borderRadius = '8px';
              retryBtn.style.background = 'rgba(11, 39, 59, 0.95)';
              retryBtn.style.color = '#DCEBFA';
              retryBtn.style.fontSize = '0.68rem';
              retryBtn.style.fontWeight = '700';
              retryBtn.style.padding = '0.18rem 0.42rem';
              retryBtn.addEventListener('click', function () {
                retryQueuedAction(entry).catch(function () {
                  showToast('Unable to retry this queued action.', true);
                });
              });

              rowActions.appendChild(retryBtn);
            }

            const discardBtn = document.createElement('button');
            discardBtn.type = 'button';
            discardBtn.textContent = 'Discard';
            discardBtn.style.border = '1px solid rgba(251, 113, 133, 0.52)';
            discardBtn.style.borderRadius = '8px';
            discardBtn.style.background = 'rgba(68, 16, 30, 0.9)';
            discardBtn.style.color = '#FFE1E8';
            discardBtn.style.fontSize = '0.68rem';
            discardBtn.style.fontWeight = '700';
            discardBtn.style.padding = '0.18rem 0.42rem';
            discardBtn.addEventListener('click', function () {
              discardQueuedAction(entry.id).catch(function () {
                showToast('Unable to discard this queued action.', true);
              });
            });

            rowActions.appendChild(discardBtn);

            head.appendChild(label);
            head.appendChild(badge);
            item.appendChild(head);
            item.appendChild(stamp);
            item.appendChild(state);
            item.appendChild(rowActions);
            drawerListNode.appendChild(item);
          });
        }

        const conflictCount = queued.filter(function (entry) {
          return !!entry.blocked;
        }).length;
        drawerMetaNode.textContent = 'Pending actions: ' + queued.length + ' • conflicts: ' + conflictCount + ' • ' + (navigator.onLine ? 'online' : 'offline');
      })
      .catch(function () {
        if (drawerListNode) {
          drawerListNode.innerHTML = '';
        }
        if (drawerMetaNode) {
          drawerMetaNode.textContent = 'Unable to load queued actions.';
        }
      });
  }

  function openQueueDrawer() {
    createQueueDrawer();
    drawerBackdropNode.style.display = 'block';
    drawerNode.style.display = 'flex';
    renderQueueDrawer();
  }

  function closeQueueDrawer() {
    if (!drawerNode || !drawerBackdropNode) {
      return;
    }
    drawerNode.style.display = 'none';
    drawerBackdropNode.style.display = 'none';
  }

  function readLastSyncAt() {
    try {
      return window.localStorage.getItem(LAST_SYNC_KEY) || '';
    } catch (error) {
      return '';
    }
  }

  function writeLastSyncAt(value) {
    if (!value) {
      return;
    }
    try {
      window.localStorage.setItem(LAST_SYNC_KEY, value);
    } catch (error) {
      // Ignore local storage failures.
    }
  }

  function formatSyncTime(isoValue) {
    if (!isoValue) {
      return 'not synced yet';
    }
    const parsed = new Date(isoValue);
    if (Number.isNaN(parsed.getTime())) {
      return 'not synced yet';
    }
    return parsed.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  async function updateQueueStatus() {
    const node = createStatusNode();
    try {
      const queued = await getQueuedActions();
      const pendingCount = queued.length;
      const conflictCount = queued.filter(function (entry) {
        return !!entry.blocked;
      }).length;
      const isOnline = navigator.onLine;
      const lastSyncAt = formatSyncTime(readLastSyncAt());

      if (!pendingCount && isOnline) {
        node.style.display = 'none';
        closeQueueDrawer();
        return;
      }

      node.style.display = 'block';
      const networkLabel = isOnline ? 'Online' : 'Offline';
      const syncLabel = flushInProgress ? 'syncing...' : ('last sync ' + lastSyncAt);
      node.textContent = networkLabel + ' | queued: ' + pendingCount + ' | conflicts: ' + conflictCount + ' | ' + syncLabel;
      node.style.borderColor = isOnline
        ? 'rgba(53, 136, 183, 0.5)'
        : 'rgba(250, 204, 21, 0.58)';
    } catch (error) {
      node.style.display = 'none';
    }
  }

  function readCookie(name) {
    const cookieValue = document.cookie
      .split(';')
      .map(function (entry) {
        return entry.trim();
      })
      .find(function (entry) {
        return entry.startsWith(name + '=');
      });

    if (!cookieValue) {
      return '';
    }

    return decodeURIComponent(cookieValue.slice(name.length + 1));
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      if (!('indexedDB' in window)) {
        reject(new Error('IndexedDB is unavailable'));
        return;
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = function (event) {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        }
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error || new Error('Failed to open offline sync database'));
      };
    });
  }

  function runTransaction(mode, handler) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(STORE_NAME, mode);
        const store = tx.objectStore(STORE_NAME);
        const result = handler(store, tx);

        tx.oncomplete = function () {
          resolve(result);
        };
        tx.onerror = function () {
          reject(tx.error || new Error('Offline sync transaction failed'));
        };
      }).finally(function () {
        db.close();
      });
    });
  }

  function enqueueAction(record) {
    return runTransaction('readwrite', function (store) {
      store.add(record);
    });
  }

  function getQueuedActions() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.getAll();

        request.onsuccess = function () {
          const results = Array.isArray(request.result) ? request.result : [];
          results.sort(function (a, b) {
            return Number(a.id || 0) - Number(b.id || 0);
          });
          resolve(results);
        };

        request.onerror = function () {
          reject(request.error || new Error('Failed to read offline action queue'));
        };

        tx.oncomplete = function () {
          db.close();
        };
      });
    });
  }

  function deleteQueuedAction(id) {
    return runTransaction('readwrite', function (store) {
      store.delete(id);
    });
  }

  function normalizePairs(formData) {
    const pairs = [];
    let hasUpload = false;

    formData.forEach(function (value, key) {
      if (value instanceof File) {
        if (value.name) {
          hasUpload = true;
        }
        return;
      }
      pairs.push([String(key), String(value)]);
    });

    return { pairs: pairs, hasUpload: hasUpload };
  }

  function withFreshCsrf(pairs) {
    const freshToken = readCookie('csrftoken');
    if (!freshToken) {
      return pairs;
    }

    let replaced = false;
    const updated = pairs.map(function (pair) {
      if (pair[0] === 'csrfmiddlewaretoken') {
        replaced = true;
        return [pair[0], freshToken];
      }
      return pair;
    });

    if (!replaced) {
      updated.push(['csrfmiddlewaretoken', freshToken]);
    }

    return updated;
  }

  async function replayAction(record) {
    const params = new URLSearchParams();
    withFreshCsrf(Array.isArray(record.pairs) ? record.pairs : []).forEach(function (pair) {
      params.append(pair[0], pair[1]);
    });

    const response = await fetch(record.actionUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-Requested-With': 'FluidNotesOfflineSync'
      },
      body: params.toString()
    });

    if (!response.ok) {
      const error = new Error('Replay request failed with status ' + response.status);
      error.status = response.status;
      error.isConflict = isConflictStatus(response.status);
      throw error;
    }
  }

  async function flushQueue() {
    if (flushInProgress || !navigator.onLine) {
      return;
    }

    flushInProgress = true;
    await updateQueueStatus();
    try {
      const queued = await getQueuedActions();
      if (!queued.length) {
        writeLastSyncAt(new Date().toISOString());
        return;
      }

      let syncedCount = 0;
      for (const entry of queued) {
        if (entry.blocked) {
          continue;
        }

        try {
          await replayAction(entry);
          await deleteQueuedAction(entry.id);
          syncedCount += 1;
        } catch (error) {
          console.warn('Fluid Notes offline replay paused.', error);
          const nextAttempts = Number(entry.attempts || 0) + 1;
          const mustBlock = !!error.isConflict || nextAttempts >= MAX_RETRY_ATTEMPTS;
          const updatedEntry = Object.assign({}, entry, {
            attempts: nextAttempts,
            blocked: mustBlock,
            conflict: mustBlock,
            lastError: error && error.message ? error.message : 'Replay failed'
          });

          await putQueuedAction(updatedEntry);

          if (mustBlock) {
            showToast('A queued action needs review. Open Offline Queue details.', true);
            continue;
          }

          break;
        }
      }

      if (syncedCount > 0) {
        writeLastSyncAt(new Date().toISOString());
        showToast('Offline changes synced: ' + syncedCount, false);
      }
    } finally {
      flushInProgress = false;
      await updateQueueStatus();
    }
  }

  function attachOfflineQueueing() {
    document.addEventListener('submit', function (event) {
      if (navigator.onLine) {
        return;
      }

      const form = event.target;
      if (!(form instanceof HTMLFormElement)) {
        return;
      }

      const method = String(form.method || 'get').toUpperCase();
      if (method !== 'POST') {
        return;
      }

      if (!form.action) {
        return;
      }

      const formData = new FormData(form);
      const normalized = normalizePairs(formData);
      if (normalized.hasUpload) {
        event.preventDefault();
        showToast(FILE_UPLOAD_WARNING, true);
        return;
      }

      event.preventDefault();
      const record = buildQueueRecord(form.action, normalized.pairs);

      enqueueAction(record)
        .then(function () {
          return coalesceQueue(record);
        })
        .then(function () {
          showToast('Offline: change queued. It will sync once you reconnect.', false);
          updateQueueStatus();
          if (drawerNode && drawerNode.style.display !== 'none') {
            renderQueueDrawer();
          }
        })
        .catch(function (error) {
          console.warn('Fluid Notes failed to queue offline change.', error);
          showToast('Offline queue failed. Please retry when online.', true);
        });
    }, true);
  }

  function init() {
    if (!shouldHandleCurrentPath()) {
      return;
    }

    attachOfflineQueueing();

    window.addEventListener('online', function () {
      updateQueueStatus();
      flushQueue();
    });

    window.addEventListener('offline', function () {
      updateQueueStatus();
    });

    updateQueueStatus();

    if (navigator.onLine) {
      flushQueue();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
