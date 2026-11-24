from django import forms

from .models import College, Plan, SupportTicket, TicketReply


class CollegeForm(forms.ModelForm):
    class Meta:
        model = College
        fields = ["name", "slug", "domain", "contact_email", "contact_phone", "plan", "status",
                  "subscription_started_on", "subscription_expires_on", "student_limit",
                  "backup_path", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "subscription_started_on": forms.DateInput(attrs={"type": "date"}),
            "subscription_expires_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_slug(self):
        slug = self.cleaned_data["slug"].strip().lower()
        if not slug.isidentifier() and not slug.replace("-", "").isalnum():
            raise forms.ValidationError("Slug may contain letters, digits and dashes only.")
        return slug


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ["name", "code", "price_monthly", "student_limit", "features", "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2}),
                   "features": forms.Textarea(attrs={"rows": 3})}

    def clean_features(self):
        data = self.cleaned_data["features"] or []
        if isinstance(data, str):
            data = [part.strip() for part in data.replace("\n", ",").split(",") if part.strip()]
        from .models import MODULES

        valid = {code for code, _ in MODULES}
        unknown = [code for code in data if code not in valid]
        if unknown:
            raise forms.ValidationError(f"Unknown modules: {', '.join(unknown)}")
        return list(dict.fromkeys(data))


class TicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["college", "subject", "body", "opened_by", "priority"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}


class TicketReplyForm(forms.ModelForm):
    class Meta:
        model = TicketReply
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "Reply to the college…"})}
