from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    # Language switch (Django's built-in set_language view)
    path('i18n/', include('django.conf.urls.i18n')),
    path('platform/', include('platform_admin.urls')),
    path('platform/metrics/<slug:slug>/',
         __import__('platform_admin.views', fromlist=['metrics_endpoint']).metrics_endpoint,
         name='platform_metrics'),
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('student_login'), name='home'),
    path('', include('students.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
