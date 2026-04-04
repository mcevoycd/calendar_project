// static/dashboard/js/calendar.js
console.log('calendar.js loaded');
document.addEventListener('DOMContentLoaded', function () {
  const calendarEl = document.getElementById('calendar');
  if (!calendarEl) {
    console.error('calendar element not found');
    return;
  }

  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    events: '/api/events/',
    eventClick: function (info) {
      const eventId = info.event.id;
      window.location.href = `/diary/event/${eventId}/`;
    },
    dateClick: function (info) {
      // info.dateStr is YYYY-MM-DD
      window.location.href = `/diary/${info.dateStr}/`;
    }
  });

  calendar.render();
});
