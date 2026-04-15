(function () {
  const COMPONENT_SELECTORS = {
    FNCard: [
      '.panel',
      '.section-pane',
      '.notes-panel',
      '.dashboard-panel',
      '.todo-panel',
      '.todo-section-column',
      '.quick-add-panel',
      '.dialog-card',
      '.iphone-diary-events-panel',
      '.week-panel',
      '.account-panel'
    ],
    FNButton: [
      'button',
      '.btn',
      '.btn-outline',
      '.btn-canvas',
      '.pill-btn',
      '.tool-btn',
      '.mobile-icon-btn',
      '.tiny-icon-btn',
      '.btn-modal',
      '.btn-modal-primary',
      '.mobile-bottom-link',
      '.mobile-bottom-btn'
    ],
    FNInput: [
      'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])',
      'textarea',
      'select',
      '.form-control',
      '.quick-add-input',
      '.dialog-input',
      '.ios-search',
      '.todo-section-title-input'
    ],
    FNModal: ['.app-modal', '.app-modal-dialog', '.dialog-card'],
    FNListItem: ['.note-item', '.category-item', '.todo-task'],
    FNHeader: ['.section-topbar', '.notes-topbar', '.pane-head', '.topbar', '.todo-section-head'],
    FNNavBar: ['[data-mobile-nav]', '.mobile-bottom-bar']
  };

  function applyComponentClasses(root) {
    const scope = root || document;
    Object.entries(COMPONENT_SELECTORS).forEach(function ([className, selectors]) {
      scope.querySelectorAll(selectors.join(',')).forEach(function (element) {
        element.classList.add(className);
      });
    });
  }

  function applyButtonVariants() {
    document.querySelectorAll('.FNButton').forEach(function (button) {
      const text = (button.textContent || '').trim().toLowerCase();
      if (
        button.classList.contains('btn-primary')
        || button.classList.contains('mobile-bottom-btn-primary')
        || button.type === 'submit'
        || /save|add|create|quick add|new/.test(text)
      ) {
        button.classList.add('FNButton--primary');
      }

      if (
        button.classList.contains('tool-btn')
        || button.classList.contains('mobile-icon-btn')
        || button.classList.contains('tiny-icon-btn')
      ) {
        button.classList.add('FNButton--ghost');
      }
    });
  }

  function applyViewportMode() {
    if (!document.body) {
      return;
    }

    const width = window.innerWidth;
    const viewport = width <= 599 ? 'phone' : width <= 1024 ? 'tablet' : 'desktop';
    document.body.classList.add('fn-app');
    document.body.setAttribute('data-fn-viewport', viewport);
  }

  function init() {
    applyViewportMode();
    applyComponentClasses(document);
    applyButtonVariants();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  window.addEventListener('resize', applyViewportMode, { passive: true });
})();
