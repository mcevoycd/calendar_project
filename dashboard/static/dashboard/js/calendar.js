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
    initialView: 'dayGridMonth',
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
    eventContent: function(arg) {
      return { html: '<div class="fc-event-dot-custom" title="' + arg.event.title + '"></div>' };
    },
    eventClick: function (info) {
      const eventId = info.event.id;
      window.location.href = `/diary/event/${eventId}/`;
    },
    dateClick: function (info) {
      window.location.href = `/diary/${info.dateStr}/`;
    }
  });

  calendar.render();
});
