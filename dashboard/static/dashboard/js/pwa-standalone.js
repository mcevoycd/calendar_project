(function () {
  const STANDALONE_QUERY = '(display-mode: standalone)';
  const SERVICE_WORKER_URL = '/service-worker.js';

  function isStandaloneMode() {
    try {
      return Boolean((window.matchMedia && window.matchMedia(STANDALONE_QUERY).matches) || window.navigator.standalone === true);
    } catch (error) {
      return false;
    }
  }

  function applyStandaloneClass() {
    const standalone = isStandaloneMode();
    document.documentElement.classList.toggle('pwa-standalone', standalone);
    if (document.body) {
      document.body.classList.toggle('pwa-standalone', standalone);
    }
  }

  async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      return;
    }

    try {
      await navigator.serviceWorker.register(SERVICE_WORKER_URL, { scope: '/' });
    } catch (error) {
      console.warn('Fluid Notes PWA service worker registration failed.', error);
    }
  }

  function shouldInterceptNavigation(link, event) {
    if (!link || !isStandaloneMode()) {
      return false;
    }

    if (event.defaultPrevented || event.button !== 0) {
      return false;
    }

    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return false;
    }

    if (link.target && link.target !== '_self') {
      return false;
    }

    if (link.hasAttribute('download')) {
      return false;
    }

    const href = link.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) {
      return false;
    }

    const nextUrl = new URL(link.href, window.location.href);
    if (nextUrl.origin !== window.location.origin) {
      return false;
    }

    return true;
  }

  async function softNavigate(url, replaceState) {
    if (!isStandaloneMode()) {
      window.location.assign(url);
      return;
    }

    try {
      const response = await fetch(url, {
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'FluidNotesPWA'
        }
      });

      const contentType = response.headers.get('content-type') || '';
      if (!response.ok || !contentType.includes('text/html')) {
        window.location.assign(url);
        return;
      }

      const html = await response.text();
      const nextUrl = new URL(url, window.location.href).toString();

      if (replaceState) {
        window.history.replaceState({ pwa: true }, '', nextUrl);
      } else {
        window.history.pushState({ pwa: true }, '', nextUrl);
      }

      document.open();
      document.write(html);
      document.close();
    } catch (error) {
      console.warn('Fluid Notes standalone navigation fallback triggered.', error);
      window.location.assign(url);
    }
  }

  document.addEventListener('click', function (event) {
    const link = event.target.closest('a[href]');
    if (!shouldInterceptNavigation(link, event)) {
      return;
    }

    event.preventDefault();
    softNavigate(link.href, false);
  }, true);

  window.addEventListener('popstate', function () {
    if (isStandaloneMode()) {
      softNavigate(window.location.href, true);
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyStandaloneClass, { once: true });
  } else {
    applyStandaloneClass();
  }

  window.addEventListener('pageshow', applyStandaloneClass);
  window.addEventListener('resize', applyStandaloneClass);
  registerServiceWorker();
})();
