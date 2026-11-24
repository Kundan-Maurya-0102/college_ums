"""Create the default Basic / Pro / Enterprise plans (idempotent)."""
from django.core.management.base import BaseCommand

from platform_admin.models import Plan

DEFAULT_PLANS = [
    {
        "name": "Basic", "code": "basic", "price_monthly": 1999, "student_limit": 500,
        "features": ["students", "attendance", "marks", "notices"],
    },
    {
        "name": "Pro", "code": "pro", "price_monthly": 4999, "student_limit": 2000,
        "features": ["students", "attendance", "marks", "fees", "notices", "reports",
                     "whatsapp", "parent_portal"],
    },
    {
        "name": "Enterprise", "code": "enterprise", "price_monthly": 9999, "student_limit": 10000,
        "features": ["students", "attendance", "marks", "fees", "notices", "reports",
                     "whatsapp", "parent_portal", "ai_chatbot", "online_payment"],
    },
]


class Command(BaseCommand):
    help = "Seed the default subscription plans"

    def handle(self, *args, **options):
        for spec in DEFAULT_PLANS:
            plan, created = Plan.objects.update_or_create(code=spec["code"], defaults=spec)
            self.stdout.write(f"{'created' if created else 'updated'}: {plan.name} "
                              f"({len(plan.features)} modules, limit {plan.student_limit})")
