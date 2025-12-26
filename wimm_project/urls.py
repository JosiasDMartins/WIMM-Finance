"""
URL configuration for wimm_project project.

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
# Django admin is disabled - SweetMoney uses a custom family-based permission system
# from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    # Django admin disabled - not used by SweetMoney
    # path('admin/', admin.site.urls),

    #Authentication routes (login, logout, password_reset and etc)
    path('', include('django.contrib.auth.urls')),

    # i18n language switching
    path('i18n/', include('django.conf.urls.i18n')),

    # PWA (Progressive Web App) support - using custom views with dynamic versioning
    # path('', include('pwa.urls')),  # Replaced with custom views in finances.urls

    #include WIMM routes
    path('', include('finances.urls')),

]
