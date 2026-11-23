"""Small UI helpers shared by templates."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Rebuild the current querystring with ``kwargs`` applied.

    Used by the pagination partial so filters/search survive page changes.
    """
    request = context.get("request")
    query = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag(takes_context=True)
def nav_active(context, *names, prefix=""):
    """Return "active" when the current url name matches, plus a prefix match."""
    match = getattr(context.get("request"), "resolver_match", None)
    url_name = getattr(match, "url_name", "") or ""
    if url_name in names or (prefix and url_name.startswith(prefix)):
        return "active"
    return ""
