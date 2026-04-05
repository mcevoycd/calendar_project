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
    initialView: 'dayGridMonth',
    height: 'auto',
    contentHeight: 'auto',
    expandRows: true,
    firstDay: 1,
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,timeGridDay'
    },
    buttonText: {
      today: 'Today',
      month: 'Month',
      week: 'Week',
      day: 'Day'
    },
    events: '/api/events/',
    eventDisplay: 'block',
    eventClick: function (info) {
      const eventDate = info.event.startStr ? info.event.startStr.slice(0, 10) : '';
      window.location.href = eventDate ? `/diary/?date=${eventDate}` : '/diary/';
    },
    dateClick: function (info) {
      window.location.href = `/diary/?date=${info.dateStr}`;
    }
  });

  calendar.render();
});
