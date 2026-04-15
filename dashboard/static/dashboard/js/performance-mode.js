(function () {
  const STORAGE_KEY = 'fluid-performance-mode';

  function getInitialValue() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === '1' || saved === '0') {
        return saved === '1';
      }
    } catch (error) {
      // Ignore storage access errors.
    }

    const prefersReducedMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const lowPowerDevice = (typeof navigator.deviceMemory === 'number' && navigator.deviceMemory <= 4)
      || (typeof navigator.hardwareConcurrency === 'number' && navigator.hardwareConcurrency <= 4);

    return !!(prefersReducedMotion || lowPowerDevice);
  }

  function updateButtons(enabled) {
    document.querySelectorAll('[data-performance-toggle]').forEach(function (btn) {
      btn.classList.toggle('is-active', enabled);
      btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      btn.textContent = enabled ? 'Fast Mode: On' : 'Fast Mode: Off';
    });
  }

  function applyPerformanceMode(enabled, persist) {
    if (!document.body) {
      return;
    }

    document.body.classList.toggle('performance-mode', enabled);
    updateButtons(enabled);

    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
      } catch (error) {
        // Ignore storage access errors.
      }
    }
  }

  function init() {
    const initialValue = getInitialValue();
    applyPerformanceMode(initialValue, false);

    document.querySelectorAll('[data-performance-toggle]').forEach(function (btn) {
      if (btn.dataset.performanceModeBound === '1') {
        return;
      }

      btn.dataset.performanceModeBound = '1';
      btn.addEventListener('click', function () {
        const nextValue = !document.body.classList.contains('performance-mode');
        applyPerformanceMode(nextValue, true);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
