# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/events/', views.events_api, name='events_api'),
    path('diary/<str:date>/', views.diary_view, name='diary_by_date'),
    path('diary/event/<int:event_id>/', views.diary_view, name='diary_by_event'),
]
