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
