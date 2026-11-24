"""Public, unauthenticated forms (landing page, bug reports)."""
from django import forms

from platform_admin.models import DemoRequest
from students.models import BugReport


class DemoRequestForm(forms.ModelForm):
    class Meta:
        model = DemoRequest
        fields = ["college_name", "contact_name", "email", "phone", "students", "message"]
        widgets = {
            "college_name": forms.TextInput(attrs={"class": "form-control",
                                                   "placeholder": "Government Polytechnic, Gaya"}),
            "contact_name": forms.TextInput(attrs={"class": "form-control",
                                                   "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"class": "form-control",
                                             "placeholder": "principal@college.ac.in"}),
            "phone": forms.TextInput(attrs={"class": "form-control",
                                            "placeholder": "10-digit mobile"}),
            "students": forms.NumberInput(attrs={"class": "form-control",
                                                 "placeholder": "e.g. 480"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                             "placeholder": "What would you like to see in the demo?"}),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if phone and len(digits) < 10:
            raise forms.ValidationError("Enter a 10-digit mobile number, or leave it blank.")
        return digits

    def clean_college_name(self):
        name = self.cleaned_data["college_name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Please write the full college name.")
        return name


class BugReportForm(forms.ModelForm):
    class Meta:
        model = BugReport
        fields = ["category", "message"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={
                "class": "form-control", "rows": 4, "required": True,
                "placeholder": "What happened? What did you expect instead?",
            }),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write at least a sentence so we can reproduce it.")
        return message
