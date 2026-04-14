"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from dashboard import views as dashboard_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.json', dashboard_views.pwa_manifest, name='pwa-manifest'),
    path('service-worker.js', dashboard_views.pwa_service_worker, name='pwa-service-worker'),
    path('icons/<str:filename>', dashboard_views.pwa_icon, name='pwa-icon'),
    path('accounts/login/', dashboard_views.auth_view, name='login'),
    path('accounts/signup/', dashboard_views.signup_view, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    path('', include('dashboard.urls')),
]
