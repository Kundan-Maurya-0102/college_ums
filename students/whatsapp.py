import logging

from django.conf import settings

from .password_links import build_set_password_link

logger = logging.getLogger(__name__)


def send_whatsapp_credentials(profile) -> str:
    """
    Send WhatsApp message with set-password link via Twilio.
    Uses secure one-time link instead of plaintext passwords.
    Returns a status string.
    """
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')

    if not sid or not token:
        logger.info("WhatsApp skipped: Twilio credentials not configured.")
        return "skipped (no credentials)"

    phone = profile.phone.strip()
    if not phone.startswith('+'):
        phone = f"+91{phone}"  # Default to India country code

    to_whatsapp = f"whatsapp:{phone}"
    from_whatsapp = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    college_name = getattr(settings, 'COLLEGE_NAME', '') or 'Student Portal'

    set_password_link = build_set_password_link(profile.user)

    message_body = (
        f"🎓 *{college_name} — Student Portal*\n\n"
        f"Hello *{profile.name}*! Your portal account is ready.\n\n"
        f"👤 *Username:* {profile.registration_number.lower()}\n"
        f"🔑 *Set Password:* {set_password_link}\n\n"
        f"Please click the link above to set your password and log in.\n"
        f"📞 Contact admin if you face any issues."
    )

    try:
        from twilio.rest import Client
        timeout = getattr(settings, 'HTTP_TIMEOUT', 10)
        client = Client(sid, token, timeout=timeout)
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp,
            to=to_whatsapp,
        )
        logger.info(f"WhatsApp sent to {phone}, SID: {message.sid}")
        return f"sent (SID: {message.sid})"
    except Exception as e:
        logger.error(f"WhatsApp failed for {phone}: {e}")
        return f"failed: {str(e)[:80]}"
