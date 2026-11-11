from django.urls import reverse

from .services.catalog import BEACH_POINTS_BY_SLUG


def favorite_undo(request):
    """Expose a one-shot undo offer after a favorite was removed without JavaScript.

    Like the messages framework, the offer is consumed by the first rendered page.
    """
    session = getattr(request, "session", None)
    slug = session.pop("favorite_undo", None) if session is not None else None
    beach = BEACH_POINTS_BY_SLUG.get(slug) if slug else None
    if beach is None:
        return {}
    return {
        "favorite_undo": {
            "name": beach.display_name,
            "restore_url": reverse("favorite_restore", args=[beach.slug]),
        }
    }
