import csv
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

from .models import (
    Assignment,
    Attendance,
    BannerImage,
    ClassSchedule,
    CSVUpload,
    Doubt,
    DoubtReply,
    Event,
    ExamSchedule,
    FacultyProfile,
    Feedback,
    FeePayment,
    FeeStructure,
    InternalExam,
    LeaveApplication,
    Notice,
    StudentProfile,
    StudyMaterial,
    Subject,
)
from .security import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, validate_upload


class CSVUploadForm(forms.ModelForm):
    class Meta:
        model = CSVUpload
        fields = ['upload_type', 'file', 'description']
        widgets = {
            'upload_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. CS Branch Semester 3 - Batch 2024',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv',
                'id': 'csvFileInput',
            }),
        }

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if not f:
            return f
        if not f.name.lower().endswith('.csv'):
            raise forms.ValidationError("Only .csv files are allowed.")

        max_mb = int(getattr(settings, 'CSV_MAX_UPLOAD_MB', 5))
        if f.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f"File size must be under {max_mb} MB.")
        if f.size == 0:
            raise forms.ValidationError("The uploaded file is empty.")

        # Sniff the content instead of trusting the file extension: reject
        # binary payloads and files that are not real delimited text.
        head = f.read(8192)
        f.seek(0)
        if b'\x00' in head:
            raise forms.ValidationError("This file looks binary, not a CSV text file.")
        try:
            text = head.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise forms.ValidationError("CSV must be UTF-8 encoded text.")

        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error:
            raise forms.ValidationError(
                "Could not detect CSV columns. Upload a comma-separated file with a header row."
            )

        lines = text.splitlines()
        if not lines:
            raise forms.ValidationError("The uploaded file is empty.")
        try:
            header = next(csv.reader([lines[0]], dialect))
        except csv.Error:
            header = []
        if len([col for col in header if col.strip()]) < 2:
            raise forms.ValidationError(
                "CSV must have a header row with at least two columns."
            )
        return f


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'name', 'phone', 'registration_number',
            'email', 'address', 'branch', 'semester', 'year_of_admission',
            'father_name', 'mother_name', 'date_of_birth',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'year_of_admission': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2099}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class StudentSelfProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ["phone", "email", "address", "father_name", "mother_name", "date_of_birth"]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "father_name": forms.TextInput(attrs={"class": "form-control"}),
            "mother_name": forms.TextInput(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['title', 'content', 'target_branches', 'target_semesters', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'target_branches': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. CS,IT  (blank = all branches)',
            }),
            'target_semesters': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 1,2,3  (blank = all semesters)',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['branch', 'semester', 'subject_code', 'subject_name', 'credits', 'is_active']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'subject_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CS301'}),
            'subject_name': forms.TextInput(attrs={'class': 'form-control'}),
            'credits': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InternalExamForm(forms.ModelForm):
    class Meta:
        model = InternalExam
        fields = ['student', 'subject', 'exam_type', 'marks_obtained', 'max_marks', 'exam_date']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'exam_type': forms.Select(attrs={'class': 'form-select'}),
            'marks_obtained': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['student', 'subject', 'date', 'is_present', 'marked_by']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_present': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'marked_by': forms.TextInput(attrs={'class': 'form-control'}),
        }


class FacultyProfileForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        label="Teacher ID / Registration No",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., T-1411823"}),
    )
    password = forms.CharField(
        required=False,
        label="Password",
        help_text="Required only while creating a new teacher.",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "temporary password"}),
    )

    class Meta:
        model = FacultyProfile
        fields = [
            "username", "password", "name", "email", "phone", "department", "designation",
            "bio", "subjects", "can_send_notices", "can_enter_marks", "can_upload_materials", "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "department": forms.TextInput(attrs={"class": "form-control"}),
            "designation": forms.TextInput(attrs={"class": "form-control"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "subjects": forms.SelectMultiple(attrs={"class": "form-select", "size": 8}),
            "can_send_notices": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_enter_marks": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_upload_materials": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["username"].initial = self.instance.user.username
            self.fields["password"].required = False
        else:
            self.fields["password"].required = True
        self.fields["subjects"].queryset = Subject.objects.filter(is_active=True).order_by(
            "branch", "semester", "subject_code"
        )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("This username is already used.")
        return username

    def save(self, commit=True):
        subjects = self.cleaned_data.pop("subjects", None)
        username = self.cleaned_data.pop("username")
        password = self.cleaned_data.pop("password", "")
        profile = super().save(commit=False)
        if profile.pk:
            user = profile.user
            user.username = username
            if password:
                user.set_password(password)
        else:
            user = User(username=username, is_staff=True)
            user.set_password(password)
        user.first_name = profile.name
        user.email = profile.email
        if commit:
            user.save()
            if not profile.pk:
                profile.user = user
            profile.save()
            if subjects is not None:
                profile.subjects.set(subjects)
        return profile


class AssignmentForm(forms.ModelForm):
    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_upload(attachment, DOCUMENT_EXTENSIONS,
                            max_mb=getattr(settings, 'MATERIAL_MAX_UPLOAD_MB', 10),
                            label='Attachment')
        return attachment

    class Meta:
        model = Assignment
        fields = ["title", "description", "subject", "due_date", "attachment", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class StudyMaterialForm(forms.ModelForm):
    def clean_file(self):
        material = self.cleaned_data.get('file')
        if material:
            validate_upload(material, DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS,
                            max_mb=getattr(settings, 'MATERIAL_MAX_UPLOAD_MB', 10),
                            label='Study material')
        return material

    # Declared explicitly: Django 5.2 warns that the default URL scheme becomes
    # https in 6.0. Teachers paste "example.com/notes", so assume https ourselves.
    external_link = forms.URLField(
        required=False, assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "form-control"}))

    class Meta:
        model = StudyMaterial
        fields = ["title", "description", "subject", "material_type", "file", "external_link", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "material_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ClassScheduleForm(forms.ModelForm):
    class Meta:
        model = ClassSchedule
        fields = ["subject", "weekday", "start_time", "end_time", "room", "is_active"]
        widgets = {
            "subject": forms.Select(attrs={"class": "form-select"}),
            "weekday": forms.Select(attrs={"class": "form-select"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "end_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "room": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class BannerImageForm(forms.ModelForm):
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            validate_upload(image, IMAGE_EXTENSIONS,
                            max_mb=getattr(settings, 'BANNER_MAX_UPLOAD_MB', 4),
                            label='Banner image')
            try:
                from PIL import Image
                Image.open(image).verify()
            except Exception:
                raise forms.ValidationError('Banner image is not a valid image file.')
            finally:
                try:
                    image.seek(0)
                except Exception:  # pragma: no cover - stream already closed
                    logger.debug("Could not rewind uploaded banner image", exc_info=True)
        return image

    class Meta:
        model = BannerImage
        fields = ['title', 'image', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Annual Fest 2024'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DoubtForm(forms.ModelForm):
    class Meta:
        model = Doubt
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What is your doubt about?'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe your doubt in detail...'}),
        }


class DoubtReplyForm(forms.ModelForm):
    class Meta:
        model = DoubtReply
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Write your answer here...'}),
        }


class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['branch', 'semester', 'fee_type', 'amount', 'academic_year', 'is_active']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'fee_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '2024-2025'}),
            'is_active': forms.CheckboxInput(),
        }


class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['student', 'fee_structure', 'amount_paid', 'payment_date', 'receipt_number', 'payment_mode', 'status', 'remarks']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'fee_structure': forms.Select(attrs={'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_mode': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ExamScheduleForm(forms.ModelForm):
    class Meta:
        model = ExamSchedule
        fields = ['branch', 'semester', 'subject', 'exam_type', 'exam_date', 'start_time', 'end_time', 'room', 'is_active']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 6}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'exam_type': forms.Select(attrs={'class': 'form-control'}),
            'exam_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(),
        }


class LeaveApplicationForm(forms.ModelForm):
    class Meta:
        model = LeaveApplication
        fields = ['leave_type', 'from_date', 'to_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'from_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'to_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['subject', 'faculty', 'rating', 'comments']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'faculty': forms.Select(attrs={'class': 'form-control'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'event_date', 'event_type', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'event_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(),
        }


class AdminUserForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        label="Admin Username / ID",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "admin username"}),
    )
    email = forms.EmailField(
        required=False,
        label="Email Address",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "optional email"}),
    )
    password = forms.CharField(
        required=False,
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "password"}),
    )
    is_superuser = forms.BooleanField(
        required=False,
        label="Full superuser (Django admin access)",
        help_text="Grants every permission in the system. Leave unchecked for office staff.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def __init__(self, *args, allow_superuser=False, **kwargs):
        """`allow_superuser` must come from the request: only a superuser may grant it."""
        super().__init__(*args, **kwargs)
        self.allow_superuser = allow_superuser
        if self.instance and self.instance.pk:
            self.fields["password"].required = False
            self.fields["password"].help_text = "Leave blank to keep current password."
            self.fields["is_superuser"].initial = self.instance.is_superuser
        else:
            self.fields["password"].required = True
        if not allow_superuser:
            # remove, not just disable: a crafted POST must not be able to set it
            self.fields.pop("is_superuser", None)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if self.allow_superuser:
            user.is_superuser = bool(self.cleaned_data.get("is_superuser"))
        # without the flag the existing value is kept (never silently escalated)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


