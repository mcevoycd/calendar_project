(function () {
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

  function openDb() {
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
        reject(request.error || new Error('offline snapshot db open failed'));
      };
    });
  }

  function getSnapshot(section) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.get(section);
        request.onsuccess = function () {
          resolve(request.result || null);
        };
        request.onerror = function () {
          reject(request.error || new Error('offline snapshot read failed'));
        };
        tx.oncomplete = function () {
          db.close();
        };
      });
    });
  }

  function ensureStyles() {
    if (document.getElementById('offline-hydrate-styles')) {
      return;
    }

    const style = document.createElement('style');
    style.id = 'offline-hydrate-styles';
    style.textContent = [
      '.offline-snapshot-banner{margin:0 0 .8rem;padding:.62rem .75rem;border-radius:12px;border:1px solid rgba(250,204,21,.45);background:rgba(58,48,22,.86);color:#fff5cc;font-size:.8rem;font-weight:700;line-height:1.35;}',
      '.offline-inline-meta{color:#9fb7cb;font-size:.72rem;font-weight:600;}',
      '.offline-muted{color:#8fa6b9;font-size:.76rem;font-style:italic;}',
      '.offline-notes-preview{margin:0 0 .75rem;padding:.78rem;border-radius:14px;border:1px solid rgba(53,136,183,.3);background:rgba(9,27,42,.82);display:grid;gap:.42rem;}',
      '.offline-notes-preview h3{margin:0;color:#eaf4ff;font-size:.94rem;font-weight:700;}',
      '.offline-notes-preview-body{color:#d3e1ec;font-size:.78rem;line-height:1.55;max-height:18rem;overflow:auto;}',
      '.offline-static-trigger{display:block;width:100%;border:none;background:transparent;padding:0;text-align:left;color:inherit;cursor:pointer;}',
      '.offline-diary-summary{display:grid;gap:.65rem;padding:.2rem 0;}',
      '.offline-diary-day{padding:.7rem .78rem;border-radius:14px;border:1px solid rgba(53,136,183,.28);background:rgba(9,27,42,.82);display:grid;gap:.42rem;}',
      '.offline-diary-day h3{margin:0;color:#eaf4ff;font-size:.86rem;font-weight:700;}',
      '.offline-diary-day-list{list-style:none;margin:0;padding:0;display:grid;gap:.32rem;}',
      '.offline-diary-day-item{display:grid;gap:.12rem;padding:.2rem 0;border-bottom:1px solid rgba(255,255,255,.06);}',
      '.offline-diary-day-item:last-child{border-bottom:none;}',
      '.offline-diary-day-item-title{color:#eaf4ff;font-size:.78rem;font-weight:600;}',
      '.offline-diary-day-item-meta{color:#9fb7cb;font-size:.72rem;}',
      '.offline-hidden-while-offline{display:none !important;}',
      '@media (max-width: 599px){.offline-notes-preview{padding:.72rem;}.offline-diary-day{padding:.65rem .7rem;}}'
    ].join('');
    document.head.appendChild(style);
  }

  function formatDateTime(isoValue) {
    if (!isoValue) {
      return 'unknown';
    }
    const parsed = new Date(isoValue);
    if (Number.isNaN(parsed.getTime())) {
      return 'unknown';
    }
    return parsed.toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function formatDiaryStamp(entry) {
    const dateText = entry && entry.date ? entry.date : '';
    const startTime = entry && entry.start_time ? entry.start_time : '';
    if (!dateText) {
      return 'Unknown date';
    }
    return startTime ? (dateText + ' · ' + startTime) : (dateText + ' · All day');
  }

  function createBanner(message) {
    const main = document.querySelector('.main');
    if (!main) {
      return;
    }

    let banner = document.getElementById('offline-snapshot-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'offline-snapshot-banner';
      banner.className = 'offline-snapshot-banner';
      main.insertBefore(banner, main.firstChild);
    }
    banner.textContent = message;
  }

  function clearChildren(node) {
    if (!node) {
      return;
    }
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function buildTodoTaskNode(task, isCompleted) {
    const item = document.createElement('li');
    item.className = 'todo-task';

    const hit = document.createElement('div');
    hit.className = 'todo-task-hit' + (isCompleted ? ' is-completed' : '');

    const priority = document.createElement('span');
    priority.className = 'todo-priority todo-priority-' + String(task.priority || 'medium');
    priority.textContent = String(task.priority_label || task.priority || 'Medium');

    const title = document.createElement('span');
    title.className = 'todo-task-title';
    title.textContent = String(task.title || 'Untitled task');

    const date = document.createElement('span');
    date.className = 'todo-task-date';
    date.textContent = String(task.date_range_label || task.start_date || '');

    hit.appendChild(priority);
    hit.appendChild(title);
    hit.appendChild(date);

    if (task.checklist && task.checklist.length) {
      const checklist = document.createElement('span');
      checklist.className = 'todo-task-checklist-meta';
      checklist.textContent = String(task.checklist.length) + ' checklist item' + (task.checklist.length === 1 ? '' : 's');
      hit.appendChild(checklist);
    }

    if (task.notes) {
      const notes = document.createElement('span');
      notes.className = 'todo-task-notes';
      notes.textContent = String(task.notes);
      hit.appendChild(notes);
    }

    item.appendChild(hit);
    return item;
  }

  function renderTodoInPlace(snapshot) {
    const payload = snapshot && snapshot.payload;
    const grid = document.querySelector('.todo-sections-grid');
    if (!payload || !Array.isArray(payload.sections) || !grid) {
      return;
    }

    clearChildren(grid);
    grid.setAttribute('aria-label', 'Offline To Do snapshot');

    payload.sections.forEach(function (section) {
      const column = document.createElement('article');
      column.className = 'todo-section-column ' + String(section.class_name || '');
      column.setAttribute('aria-label', String(section.name || 'Section') + ' offline tasks');

      const header = document.createElement('header');
      header.className = 'todo-section-head';
      const title = document.createElement('div');
      title.className = 'todo-section-title-btn';
      title.textContent = String(section.name || 'Section');
      header.appendChild(title);
      column.appendChild(header);

      const body = document.createElement('div');
      body.className = 'todo-section-body';

      const activeTasks = Array.isArray(section.active_tasks) ? section.active_tasks : [];
      if (activeTasks.length) {
        const list = document.createElement('ul');
        list.className = 'todo-section-tasks';
        activeTasks.forEach(function (task) {
          list.appendChild(buildTodoTaskNode(task, false));
        });
        body.appendChild(list);
      } else {
        const empty = document.createElement('div');
        empty.className = 'todo-empty';
        empty.textContent = 'No active tasks in local snapshot.';
        body.appendChild(empty);
      }

      const completedTasks = Array.isArray(section.completed_tasks) ? section.completed_tasks : [];
      if (completedTasks.length) {
        const archive = document.createElement('details');
        archive.className = 'todo-archive';
        archive.open = true;
        const summary = document.createElement('summary');
        summary.className = 'todo-archive-summary';
        summary.textContent = 'Archive / Completed (' + completedTasks.length + ')';
        archive.appendChild(summary);

        const archiveList = document.createElement('ul');
        archiveList.className = 'todo-archive-list';
        completedTasks.forEach(function (task) {
          archiveList.appendChild(buildTodoTaskNode(task, true));
        });
        archive.appendChild(archiveList);
        body.appendChild(archive);
      }

      column.appendChild(body);
      grid.appendChild(column);
    });

    const localNav = document.getElementById('todo-local-section-nav');
    if (localNav) {
      localNav.classList.add('offline-hidden-while-offline');
    }
    const panel = document.getElementById('todo-panel');
    const backdrop = document.getElementById('todo-panel-backdrop');
    if (panel) {
      panel.classList.remove('active');
      panel.classList.add('offline-hidden-while-offline');
    }
    if (backdrop) {
      backdrop.classList.remove('active');
      backdrop.classList.add('offline-hidden-while-offline');
    }
  }

  function buildCategoryNode(label, isActive) {
    const article = document.createElement('article');
    article.className = 'category-item' + (isActive ? ' active' : '');
    const link = document.createElement('div');
    link.className = 'category-link';
    const icon = document.createElement('span');
    icon.className = 'category-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = label ? String(label).slice(0, 1).toUpperCase() : 'A';
    const strong = document.createElement('strong');
    strong.textContent = label || 'All Notes';
    link.appendChild(icon);
    link.appendChild(strong);
    article.appendChild(link);
    return article;
  }

  function renderNotePreview(previewNode, note) {
    clearChildren(previewNode);

    if (!note) {
      const empty = document.createElement('div');
      empty.className = 'offline-muted';
      empty.textContent = 'No note is available in the local snapshot.';
      previewNode.appendChild(empty);
      return;
    }

    const title = document.createElement('h3');
    title.textContent = String(note.title || 'Untitled note');

    const meta = document.createElement('div');
    meta.className = 'offline-inline-meta';
    meta.textContent = (note.category_name ? note.category_name + ' · ' : '') + 'Snapshot: ' + formatDateTime(note.updated_at);

    const body = document.createElement('div');
    body.className = 'offline-notes-preview-body';
    body.innerHTML = String(note.body || '<p>No content yet.</p>');

    previewNode.appendChild(title);
    previewNode.appendChild(meta);
    previewNode.appendChild(body);
  }

  function renderNotesInPlace(snapshot) {
    const payload = snapshot && snapshot.payload;
    if (!payload || !Array.isArray(payload.notes)) {
      return;
    }

    const desktopCategoryLists = document.querySelectorAll('.categories-pane .category-list');
    const mobileCategoryLists = document.querySelectorAll('#categories-drawer .category-list');
    const noteList = document.querySelector('.note-list');
    const notesPaneScroll = document.querySelector('.notes-pane .notes-list');
    if (!noteList || !notesPaneScroll) {
      return;
    }

    const selectedId = String(payload.selected_note_id || '');
    const notes = payload.notes.slice();
    const activeNote = notes.find(function (note) {
      return String(note.id) === selectedId;
    }) || notes[0] || null;

    function refillCategoryLists(nodeList) {
      nodeList.forEach(function (list) {
        clearChildren(list);
        list.appendChild(buildCategoryNode('All Notes', !payload.selected_category_id));
        (Array.isArray(payload.categories) ? payload.categories : []).forEach(function (category) {
          list.appendChild(buildCategoryNode(String(category.name || 'Untitled category'), String(payload.selected_category_id || '') === String(category.id || '')));
        });
      });
    }

    refillCategoryLists(desktopCategoryLists);
    refillCategoryLists(mobileCategoryLists);

    let preview = document.getElementById('offline-notes-preview');
    if (!preview) {
      preview = document.createElement('section');
      preview.id = 'offline-notes-preview';
      preview.className = 'offline-notes-preview';
      notesPaneScroll.insertBefore(preview, noteList);
    }

    clearChildren(noteList);
    if (!notes.length) {
      const emptyItem = document.createElement('article');
      emptyItem.className = 'note-item';
      const emptyLink = document.createElement('div');
      emptyLink.className = 'note-link';
      const emptyTitle = document.createElement('div');
      emptyTitle.className = 'note-title';
      emptyTitle.textContent = 'No notes yet';
      const emptyPreview = document.createElement('p');
      emptyPreview.className = 'note-preview';
      emptyPreview.textContent = 'No note content is available offline yet.';
      emptyLink.appendChild(emptyTitle);
      emptyLink.appendChild(emptyPreview);
      emptyItem.appendChild(emptyLink);
      noteList.appendChild(emptyItem);
    } else {
      notes.forEach(function (note) {
        const item = document.createElement('article');
        item.className = 'note-item' + (activeNote && String(activeNote.id) === String(note.id) ? ' active' : '');

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'note-link offline-static-trigger';

        const head = document.createElement('div');
        head.className = 'note-head';
        const title = document.createElement('span');
        title.className = 'note-title';
        title.textContent = String(note.title || 'Untitled note');
        const meta = document.createElement('span');
        meta.className = 'note-meta';
        meta.textContent = formatDateTime(note.updated_at);
        head.appendChild(title);
        head.appendChild(meta);

        const previewText = document.createElement('p');
        previewText.className = 'note-preview';
        const stripped = String(note.body || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
        previewText.textContent = stripped || 'No content yet.';

        button.appendChild(head);
        button.appendChild(previewText);
        button.addEventListener('click', function () {
          noteList.querySelectorAll('.note-item').forEach(function (row) {
            row.classList.remove('active');
          });
          item.classList.add('active');
          renderNotePreview(preview, note);
        });

        item.appendChild(button);
        noteList.appendChild(item);
      });
    }

    renderNotePreview(preview, activeNote);

    const editorDrawer = document.getElementById('notes-editor-drawer');
    const categoriesDrawer = document.getElementById('categories-drawer');
    const backdrop = document.getElementById('notes-backdrop');
    if (editorDrawer) {
      editorDrawer.classList.remove('active');
      editorDrawer.classList.add('offline-hidden-while-offline');
    }
    if (categoriesDrawer) {
      categoriesDrawer.classList.remove('active');
    }
    if (backdrop) {
      backdrop.classList.remove('active');
      backdrop.classList.add('offline-hidden-while-offline');
    }
  }

  function groupDiaryEntries(entries) {
    const orderedKeys = [];
    const groups = new Map();
    entries.forEach(function (entry) {
      const key = String(entry.date || 'Unknown date');
      if (!groups.has(key)) {
        groups.set(key, []);
        orderedKeys.push(key);
      }
      groups.get(key).push(entry);
    });
    return orderedKeys.map(function (key) {
      return [key, groups.get(key)];
    });
  }

  function buildDiaryItem(entry) {
    const item = document.createElement('li');
    item.className = 'offline-diary-day-item';

    const title = document.createElement('span');
    title.className = 'offline-diary-day-item-title';
    title.textContent = String(entry.title || 'Untitled entry');

    const meta = document.createElement('span');
    meta.className = 'offline-diary-day-item-meta';
    meta.textContent = formatDiaryStamp(entry) + (entry.category ? ' · ' + entry.category : '');

    item.appendChild(title);
    item.appendChild(meta);

    if (entry.content) {
      const body = document.createElement('span');
      body.className = 'offline-diary-day-item-meta';
      body.textContent = String(entry.content).slice(0, 120);
      item.appendChild(body);
    }

    return item;
  }

  function fillSelectedDayPanel(entries, label) {
    const panel = document.getElementById('custom-selected-day-panel');
    const title = document.getElementById('custom-selected-day-title');
    const subtitle = document.getElementById('custom-selected-day-subtitle');
    const list = document.getElementById('custom-selected-day-list');
    if (!panel || !title || !subtitle || !list) {
      return;
    }

    panel.hidden = false;
    title.textContent = label || 'Offline diary entries';
    subtitle.textContent = String(entries.length) + ' entries in local snapshot';
    clearChildren(list);

    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'offline-muted';
      empty.textContent = 'No diary entries are available in the local snapshot.';
      list.appendChild(empty);
      return;
    }

    entries.slice(0, 10).forEach(function (entry) {
      list.appendChild(buildDiaryItem(entry));
    });
  }

  function renderDiaryInPlace(snapshot) {
    const payload = snapshot && snapshot.payload;
    const entries = payload && Array.isArray(payload.entries) ? payload.entries.slice() : [];
    const scrollWrapper = document.getElementById('calendar-scroll-wrapper');
    const monthEventsList = document.getElementById('iphone-diary-events-list');
    if (!scrollWrapper || !monthEventsList) {
      return;
    }

    const grouped = groupDiaryEntries(entries);

    clearChildren(scrollWrapper);
    const summary = document.createElement('section');
    summary.className = 'offline-diary-summary';

    if (!grouped.length) {
      const empty = document.createElement('div');
      empty.className = 'offline-muted';
      empty.textContent = 'No diary entries are available in the local snapshot.';
      summary.appendChild(empty);
    } else {
      grouped.slice(0, 10).forEach(function (group) {
        const day = document.createElement('article');
        day.className = 'offline-diary-day';
        const heading = document.createElement('h3');
        heading.textContent = group[0];
        day.appendChild(heading);
        const list = document.createElement('ul');
        list.className = 'offline-diary-day-list';
        group[1].slice(0, 8).forEach(function (entry) {
          list.appendChild(buildDiaryItem(entry));
        });
        day.appendChild(list);
        summary.appendChild(day);
      });
    }
    scrollWrapper.appendChild(summary);

    clearChildren(monthEventsList);
    if (!grouped.length) {
      const empty = document.createElement('div');
      empty.className = 'iphone-events-empty';
      empty.textContent = 'No diary events in local snapshot.';
      monthEventsList.appendChild(empty);
    } else {
      grouped.forEach(function (group, groupIndex) {
        const section = document.createElement('section');
        section.className = 'iphone-event-day-group' + (groupIndex === 0 ? ' is-selected' : '');
        section.setAttribute('data-group-date', group[0]);

        group[1].forEach(function (entry) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'iphone-event-card';
          button.setAttribute('aria-label', String(entry.title || 'Entry') + ' on ' + group[0]);

          const time = document.createElement('div');
          time.className = 'iphone-event-time';
          time.textContent = formatDiaryStamp(entry);

          const title = document.createElement('div');
          title.className = 'iphone-event-title';
          title.textContent = String(entry.title || 'Untitled entry');

          button.appendChild(time);
          button.appendChild(title);
          button.addEventListener('click', function () {
            monthEventsList.querySelectorAll('.iphone-event-day-group').forEach(function (row) {
              row.classList.remove('is-selected');
            });
            section.classList.add('is-selected');
            fillSelectedDayPanel(group[1], group[0]);
          });
          section.appendChild(button);
        });

        monthEventsList.appendChild(section);
      });
    }

    fillSelectedDayPanel(grouped.length ? grouped[0][1] : [], grouped.length ? grouped[0][0] : 'Offline diary entries');

    const controls = document.querySelector('.diary-view-controls');
    const mobileNav = document.querySelector('.mobile-calendar-nav');
    if (controls) {
      controls.classList.add('offline-hidden-while-offline');
    }
    if (mobileNav) {
      mobileNav.classList.add('offline-hidden-while-offline');
    }
  }

  function hydrateOfflineSnapshot(snapshot) {
    const section = getSectionKey();
    if (!section || !snapshot || !snapshot.payload) {
      return;
    }

    ensureStyles();
    createBanner('Offline mode is active. Showing the latest local snapshot in place for this section.');

    if (section === 'todo') {
      renderTodoInPlace(snapshot);
      return;
    }
    if (section === 'notes') {
      renderNotesInPlace(snapshot);
      return;
    }
    if (section === 'diary') {
      renderDiaryInPlace(snapshot);
    }
  }

  function init() {
    if (navigator.onLine) {
      return;
    }

    const section = getSectionKey();
    if (!section) {
      return;
    }

    getSnapshot(section)
      .then(function (snapshot) {
        if (!snapshot || !snapshot.payload) {
          createBanner('Offline mode is active, but no local snapshot is available yet for this section.');
          return;
        }
        hydrateOfflineSnapshot(snapshot);
      })
      .catch(function () {
        createBanner('Offline mode is active, but local snapshot data could not be loaded.');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
