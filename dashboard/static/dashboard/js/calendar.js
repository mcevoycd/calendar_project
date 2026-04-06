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
