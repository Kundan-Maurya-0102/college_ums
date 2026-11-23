"""Shared pagination helper: keeps list views short and consistent."""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

DEFAULT_PER_PAGE = 25


def paginate(request, queryset, per_page=DEFAULT_PER_PAGE, param="page"):
    """Return a Page for ``queryset`` using ``?page=`` from the request.

    Templates can keep iterating the same context variable, and bad/huge page
    numbers fall back to the first/last page instead of raising.
    """
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.page(request.GET.get(param, 1))
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
