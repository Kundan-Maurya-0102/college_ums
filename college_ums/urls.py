from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

urlpatterns = [
    # Language switch (Django's built-in set_language view)
    path('i18n/', include('django.conf.urls.i18n')),
    path('platform/', include('platform_admin.urls')),
    path('platform/metrics/<slug:slug>/',
         __import__('platform_admin.views', fromlist=['metrics_endpoint']).metrics_endpoint,
         name='platform_metrics'),
    path('admin/', admin.site.urls),
    # Public landing page for visitors; signed-in users are redirected to their panel.
    path('', __import__('students.views', fromlist=['landing_page']).landing_page, name='home'),
    path('', include('students.urls')),
]

if settings.MEDIA_PROTECTED:
    # Uploaded files (CSV imports, assignments, banners) go through an auth check.
    urlpatterns += [re_path(r'^media/(?P<path>.*)$',
                            __import__('students.views', fromlist=['serve_media']).serve_media)]
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
