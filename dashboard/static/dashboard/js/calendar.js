// static/dashboard/js/calendar.js
console.log('calendar.js loaded');
document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) {
    console.error('calendar element not found');
    return;
  }

  function getResponsiveCalendarMode(width) {
    if (width <= 560) {
      return { view: 'dayGridMonth', columns: 1 };
    }
    if (width >= 1200) {
      return { view: 'multiMonth4', columns: 4 };
    }
    if (width <= 900) {
      return { view: 'multiMonth3', columns: 2 };
    }
    return { view: 'multiMonth3', columns: 3 };
  }

  const initialMode = getResponsiveCalendarMode(window.innerWidth);

  const calendar = new FullCalendar.Calendar(calendarEl, {
    themeSystem: 'bootstrap',
    locale: 'en-gb',
    initialView: initialMode.view,
    height: 'auto',
    contentHeight: 'auto',
    expandRows: false,
    firstDay: 1,
    multiMonthMaxColumns: initialMode.columns,
    multiMonthMinWidth: 1,
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: ''
    },
    views: {
      multiMonthYear: {
        type: 'multiMonth',
        duration: { years: 1 },
        multiMonthMaxColumns: 12,
        eventDisplay: 'none'
      },
      multiMonth6: {
        type: 'multiMonth',
        duration: { months: 6 },
        multiMonthMaxColumns: 6,
        eventDisplay: 'none'
      },
      multiMonth4: {
        type: 'multiMonth',
        duration: { months: 4 },
        multiMonthMaxColumns: 4,
        eventDisplay: 'none'
      },
      multiMonth3: {
        type: 'multiMonth',
        duration: { months: 3 },
        multiMonthMaxColumns: 3,
        eventDisplay: 'none'
      },
      dayGridMonth: {
        eventDisplay: 'block'
      }
    },
    buttonText: {
      today: 'Today',
      year: 'Year',
      month: 'Month'
    },
    events: '/api/events/',
    eventDisplay: 'block',
    eventDidMount: function (info) {
      if (info.view.type === 'multiMonthYear') {
        info.el.style.display = 'none';
        return;
      }

      // In month view, force diary/category colors onto the full event chip
      // even when FullCalendar renders a dot-style event element.
      if (info.view.type === 'dayGridMonth') {
        const bg = info.event.backgroundColor || '#38BDF8';
        const border = info.event.borderColor || bg;
        const text = info.event.textColor || '#06111E';

        info.el.style.backgroundColor = bg;
        info.el.style.borderColor = border;
        info.el.style.color = text;
        info.el.style.borderRadius = '8px';
        info.el.style.padding = '0.1rem 0.35rem';

        const main = info.el.querySelector('.fc-event-main');
        if (main) {
          main.style.color = text;
        }

        const dot = info.el.querySelector('.fc-daygrid-event-dot, .fc-event-dot');
        if (dot) {
          dot.style.display = 'none';
        }
      }
    },
    datesSet: function (info) {
      const inYearView = info.view.type === 'multiMonthYear';
      calendarEl.classList.toggle('is-year-view', inYearView);
    },
    eventClick: function (info) {
      if (info.view.type === 'multiMonthYear') {
        return;
      }
      const eventDate = info.event.startStr ? info.event.startStr.slice(0, 10) : '';
      window.location.href = eventDate ? `/diary/?date=${eventDate}` : '/diary/';
    },
    dateClick: function (info) {
      window.location.href = `/diary/?date=${info.dateStr}`;
    }
  });

  calendar.render();
  calendarEl.style.setProperty('--calendar-columns', String(initialMode.columns));

  let resizeTimer = null;
  window.addEventListener('resize', function () {
    if (resizeTimer) {
      clearTimeout(resizeTimer);
    }

    resizeTimer = setTimeout(function () {
      const mode = getResponsiveCalendarMode(window.innerWidth);
      calendar.setOption('multiMonthMaxColumns', mode.columns);
      calendarEl.style.setProperty('--calendar-columns', String(mode.columns));
      if (calendar.view.type !== mode.view) {
        calendar.changeView(mode.view);
      }
    }, 150);
  });
});
