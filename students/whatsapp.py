import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp_credentials(profile, password: str) -> str:
    """
    Send WhatsApp message with login credentials via Twilio.
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
    portal_url = getattr(settings, 'PORTAL_URL', 'http://127.0.0.1:8000')
    college_name = getattr(settings, 'COLLEGE_NAME', 'College UMS')

    message_body = (
        f"🎓 *{college_name} — Student Portal*\n\n"
        f"Hello *{profile.name}*! Your login credentials are ready.\n\n"
        f"🔗 *Portal:* {portal_url}/login/\n"
        f"👤 *Username:* `{profile.registration_number.lower()}`\n"
        f"🔑 *Password:* `{password}`\n\n"
        f"⚠️ Please log in and change your password immediately.\n"
        f"📞 Contact admin if you face any issues."
    )

    try:
        from twilio.rest import Client
        client = Client(sid, token)
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
