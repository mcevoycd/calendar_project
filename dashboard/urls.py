# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path('account/', views.account_view, name='account'),
    path('todo/', views.todo_view, name='todo'),
    path('notes/', views.notes_view, name='notes'),
    path('canvas/', views.canvas_view, name='canvas'),
    path('api/events/', views.events_api, name='events_api'),
    path('api/diary/', views.diary_api, name='diary_api'),
    path('diary/add/', views.add_diary_entry, name='add_diary_entry'),
    path('diary/delete/', views.delete_diary_entry, name='delete_diary_entry'),
    path('diary/', views.diary_view, name='diary'),
]
