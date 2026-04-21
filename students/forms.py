from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm

from .models import (Assignment, Attendance, BannerImage, ClassSchedule, CSVUpload,
                     Doubt, DoubtReply, FacultyProfile, InternalExam, Notice, SemesterResult,
                     StudentProfile, StudyMaterial, Subject)


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
        if f:
            if not f.name.endswith('.csv'):
                raise forms.ValidationError("Only CSV files are allowed.")
            if f.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 10 MB.")
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
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "teacher username"}),
    )
    password = forms.CharField(
        required=False,
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
            profile.user = user
        user.first_name = profile.name
        user.email = profile.email
        if commit:
            user.save()
            profile.save()
            if subjects is not None:
                profile.subjects.set(subjects)
        return profile


class AssignmentForm(forms.ModelForm):
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
    class Meta:
        model = StudyMaterial
        fields = ["title", "description", "subject", "material_type", "file", "external_link", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "subject": forms.Select(attrs={"class": "form-select"}),
            "material_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "external_link": forms.URLInput(attrs={"class": "form-control"}),
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
