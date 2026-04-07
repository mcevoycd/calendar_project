// static/dashboard/js/calendar.js
console.log('calendar.js loaded');
document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) {
    console.error('calendar element not found');
    return;
  }

  const calendar = new FullCalendar.Calendar(calendarEl, {
    themeSystem: 'bootstrap',
    locale: 'en-gb',
    initialView: 'multiMonthYear',
    height: '78vh',
    contentHeight: '78vh',
    expandRows: true,
    firstDay: 1,
    multiMonthMaxColumns: 3,
    multiMonthMinWidth: 1,
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'multiMonthYear,dayGridMonth'
    },
    views: {
      multiMonthYear: {
        type: 'multiMonth',
        duration: { years: 1 },
        buttonText: 'Year',
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
});
