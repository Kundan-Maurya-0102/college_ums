"""Platform-owner models: colleges, plans, subscriptions, usage, support tickets.

One college = one deployment = its own database, so these tables live in the
*platform* database (the owner's deployment), not inside a college's data.
"""
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone

# Module codes a plan can unlock. Templates/views check these codes.
MODULES = [
    ("students", "Student records & import"),
    ("attendance", "Attendance"),
    ("marks", "Internal marks & results"),
    ("fees", "Fees & payments"),
    ("notices", "Notices & events"),
    ("reports", "Reports"),
    ("parent_portal", "Parent portal"),
    ("whatsapp", "WhatsApp notifications"),
    ("ai_chatbot", "AI chatbot"),
    ("online_payment", "Online fee payment"),
]


class Plan(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    price_monthly = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    student_limit = models.PositiveIntegerField(default=500)
    features = models.JSONField(default=list, blank=True,
                                help_text="Module codes from MODULES, e.g. [\"fees\", \"reports\"]")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price_monthly", "name"]

    def __str__(self):
        return self.name

    def has_feature(self, code):
        return code in (self.features or [])


class College(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_EXPIRED = "expired"
    STATUS_TRIAL = "trial"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRIAL, "Trial"),
        (STATUS_EXPIRED, "Expired (read-only)"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=60, unique=True)
    domain = models.CharField(max_length=150, blank=True, help_text="ums.college.edu")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="colleges")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    subscription_started_on = models.DateField(default=date.today)
    subscription_expires_on = models.DateField(null=True, blank=True)
    student_limit = models.PositiveIntegerField(default=0,
                                                help_text="0 = use the plan limit")
    # metrics reported by the college deployment (not live cross-DB queries)
    student_count = models.PositiveIntegerField(default=0)
    active_users_30d = models.PositiveIntegerField(default=0)
    storage_bytes = models.BigIntegerField(default=0)
    last_login_at = models.DateTimeField(null=True, blank=True)
    metrics_reported_at = models.DateTimeField(null=True, blank=True)
    backup_path = models.CharField(max_length=300, blank=True,
                                   help_text="Latest backup file on the deploy host")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"], name="college_status_idx")]

    def __str__(self):
        return self.name

    # ── subscription state ────────────────────────────────────────────
    @property
    def effective_limit(self):
        if self.student_limit:
            return self.student_limit
        return self.plan.student_limit if self.plan else 0

    @property
    def is_expired(self):
        return bool(self.subscription_expires_on and self.subscription_expires_on < timezone.localdate())

    @property
    def days_to_expiry(self):
        if not self.subscription_expires_on:
            return None
        return (self.subscription_expires_on - timezone.localdate()).days

    @property
    def is_read_only(self):
        return self.status in (self.STATUS_SUSPENDED, self.STATUS_EXPIRED) or self.is_expired

    @property
    def storage_mb(self):
        return round(self.storage_bytes / (1024 * 1024), 1)

    def has_feature(self, code):
        if not self.plan:
            return False
        return self.plan.has_feature(code)

    def suspend(self, reason=""):
        self.status = self.STATUS_SUSPENDED
        if reason:
            self.notes = (self.notes + "\n" if self.notes else "") + f"[suspended] {reason}"
        self.save(update_fields=["status", "notes", "updated_at"])

    def resume(self):
        self.status = self.STATUS_EXPIRED if self.is_expired else self.STATUS_ACTIVE
        self.save(update_fields=["status", "updated_at"])


class UsageSnapshot(models.Model):
    """Per-day usage numbers so the owner can chart growth/cost."""
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name="usage")
    day = models.DateField(default=date.today)
    active_users = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    payments_count = models.PositiveIntegerField(default=0)
    api_calls = models.PositiveIntegerField(default=0)
    student_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("college", "day")]
        ordering = ["-day"]

    def __str__(self):
        return f"{self.college.slug} {self.day}"


class SupportTicket(models.Model):
    STATUS_OPEN = "open"
    STATUS_ANSWERED = "answered"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ANSWERED, "Answered"),
        (STATUS_CLOSED, "Closed"),
    ]
    PRIORITY_CHOICES = [("low", "Low"), ("normal", "Normal"), ("high", "High")]

    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=200)
    body = models.TextField()
    opened_by = models.CharField(max_length=150, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"], name="ticket_status_idx")]

    def __str__(self):
        return f"#{self.pk} {self.subject}"


class TicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.CharField(max_length=150)
    body = models.TextField()
    from_platform = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"reply to #{self.ticket_id}"


def platform_admin_required(user):
    """True for superusers and members of the 'Platform Admin' group."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=getattr(settings, "PLATFORM_ADMIN_GROUP", "Platform Admin")).exists()
