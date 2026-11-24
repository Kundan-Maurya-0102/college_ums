"""Small helper for writing audit-log rows without ever breaking a request."""
import logging

from .security import client_ip

logger = logging.getLogger(__name__)


def log_action(request, action, obj=None, detail=""):
    """Record an audit entry; failures are logged, never raised."""
    try:
        from .models import AuditLog

        AuditLog.objects.create(
            user=getattr(request, "user", None) if getattr(request, "user", None) and request.user.is_authenticated else None,
            action=action[:64],
            model_name=obj.__class__.__name__ if obj is not None else "",
            object_id=str(getattr(obj, "pk", "") or "")[:64],
            detail=(detail or "")[:2000],
            ip_address=client_ip(request) or None,
        )
    except Exception:  # pragma: no cover - audit must never break a request
        logger.exception("Could not write audit log for action %s", action)
