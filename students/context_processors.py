from django.conf import settings
from django.templatetags.static import static


def _logo_url():
    """Resolve COLLEGE_LOGO to a usable URL (absolute URL, static file, or blank)."""
    logo = (getattr(settings, "COLLEGE_LOGO", "") or "").strip()
    if not logo:
        return ""
    if logo.startswith(("http://", "https://", "/")):
        return logo
    return static(logo)


def college_settings(request):
    """Expose per-college branding so no template hardcodes it."""
    return {
        "COLLEGE_NAME": settings.COLLEGE_NAME,
        "COLLEGE_LOGO": settings.COLLEGE_LOGO,
        "COLLEGE_LOGO_URL": _logo_url(),
        "PRIMARY_COLOR": settings.PRIMARY_COLOR,
        "COLLEGE_EMAIL": settings.COLLEGE_EMAIL,
        "COLLEGE_PHONE": settings.COLLEGE_PHONE,
        "COLLEGE_ADDRESS": settings.COLLEGE_ADDRESS,
        "COLLEGE_WEBSITE": settings.COLLEGE_WEBSITE,
        "COLLEGE_AFFILIATION": settings.COLLEGE_AFFILIATION,
        "COLLEGE_ESTABLISHED": settings.COLLEGE_ESTABLISHED,
        "COLLEGE_PRINCIPAL_NAME": settings.COLLEGE_PRINCIPAL_NAME,
        "PORTAL_URL": settings.PORTAL_URL,
    }


def panel_flags(request):
    """Shell flags that every panel needs; a view may override any of them.

    Deliberately DB-free: pages that decide per college (the dashboards) pass their
    own values in the context, which wins over a context processor.
    """
    return {"show_dark_toggle": True}
