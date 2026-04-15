(function () {
  function handleQuickAdd(event) {
    event.preventDefault();

    const dashboardQuickAdd = document.getElementById('quick-add-open-btn');
    if (dashboardQuickAdd) {
      dashboardQuickAdd.click();
      return;
    }

    const url = new URL('/dashboard/', window.location.origin);
    url.searchParams.set('open_quick_add', '1');
    window.location.href = url.toString();
  }

  function initMobileBottomNav() {
    if (window.innerWidth > 599) {
      return;
    }

    document.body.classList.remove('mobile-menu-open');

    document.querySelectorAll('[data-mobile-quick-add]').forEach(function (button) {
      if (button.dataset.boundQuickAdd === '1') {
        return;
      }
      button.dataset.boundQuickAdd = '1';
      button.addEventListener('click', handleQuickAdd);
    });

    const backdrop = document.getElementById('mobile-menu-backdrop');
    const sheet = document.getElementById('mobile-menu-sheet');
    if (backdrop) {
      backdrop.remove();
    }
    if (sheet) {
      sheet.remove();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileBottomNav, { once: true });
  } else {
    initMobileBottomNav();
  }
})();
