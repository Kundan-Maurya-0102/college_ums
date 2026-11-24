from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('platform/', include('platform_admin.urls')),
    path('platform/metrics/<slug:slug>/',
         __import__('platform_admin.views', fromlist=['metrics_endpoint']).metrics_endpoint,
         name='platform_metrics'),
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('student_login'), name='home'),
    path('', include('students.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
