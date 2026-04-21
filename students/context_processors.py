from django.conf import settings

def college_settings(request):
    return {
        'COLLEGE_NAME': settings.COLLEGE_NAME,
        'PORTAL_URL': settings.PORTAL_URL,
    }
