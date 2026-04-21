from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class StudentProfile(models.Model):
    BRANCH_CHOICES = [
        ('CS', 'Computer Science'),
        ('CE', 'Civil'),
        ('EC', 'Electronics'),
        ('ME', 'Mechanical'),
        ('EE', 'Electrical'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # CSV Import Fields (Required)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    registration_number = models.CharField(max_length=20, unique=True)

    # Admin Filled Fields (Optional initially)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    branch = models.CharField(max_length=2, choices=BRANCH_CHOICES, blank=True)
    semester = models.IntegerField(null=True, blank=True)
    year_of_admission = models.IntegerField(null=True, blank=True)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # System Fields
    is_password_changed = models.BooleanField(default=False)
    credentials_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.registration_number})"

    def get_branch_display_name(self):
        return dict(self.BRANCH_CHOICES).get(self.branch, self.branch)

    def get_attendance_percentage(self, subject=None):
        """Get overall or subject-wise attendance percentage."""
        qs = Attendance.objects.filter(student=self)
        if subject:
            qs = qs.filter(subject=subject)
        total = qs.count()
        if total == 0:
            return 0
        present = qs.filter(is_present=True).count()
        return round((present / total) * 100, 1)

    def get_set_password_link(self) -> str:
        """
        Generate a one-time set-password link for this student.
        This avoids storing or exporting plaintext passwords.
        """
        from .password_links import build_set_password_link
        return build_set_password_link(self.user)


class Subject(models.Model):
    branch = models.CharField(max_length=2, choices=StudentProfile.BRANCH_CHOICES)
    semester = models.IntegerField()
    subject_code = models.CharField(max_length=10)
    subject_name = models.CharField(max_length=100)
    credits = models.IntegerField(default=4)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['branch', 'semester', 'subject_code']

    def __str__(self):
        return f"{self.subject_code} - {self.subject_name} (Sem {self.semester})"


class InternalExam(models.Model):
    EXAM_TYPES = [
        ('CA1', 'Class Assessment 1'),
        ('CA2', 'Class Assessment 2'),
        ('CA3', 'Class Assessment 3'),
        ('MSE', 'Mid Semester Exam'),
        ('ASSIGNMENT', 'Assignment'),
        ('ATTENDANCE', 'Attendance'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPES)
    marks_obtained = models.IntegerField()
    max_marks = models.IntegerField()
    exam_date = models.DateField()

    class Meta:
        unique_together = ['student', 'subject', 'exam_type']

    def __str__(self):
        return f"{self.student.name} | {self.subject.subject_code} | {self.exam_type}"

    def percentage(self):
        if self.max_marks == 0:
            return 0
        return round((self.marks_obtained / self.max_marks) * 100, 1)


class SemesterResult(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    semester = models.IntegerField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    internal_marks = models.IntegerField(default=0)
    external_marks = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0)
    grade = models.CharField(max_length=2, blank=True)
    is_pass = models.BooleanField(default=True)

    class Meta:
        unique_together = ['student', 'semester', 'subject']

    def __str__(self):
        return f"{self.student.name} | Sem {self.semester} | {self.subject.subject_code} | {self.grade}"

    def calculate_grade(self):
        pct = (self.total_marks / 100) * 100 if self.total_marks else 0
        if pct >= 90:
            return 'O'
        elif pct >= 80:
            return 'A+'
        elif pct >= 70:
            return 'A'
        elif pct >= 60:
            return 'B+'
        elif pct >= 50:
            return 'B'
        elif pct >= 40:
            return 'C'
        else:
            return 'F'

    def save(self, *args, **kwargs):
        self.total_marks = self.internal_marks + self.external_marks
        self.grade = self.calculate_grade()
        self.is_pass = self.grade != 'F'
        super().save(*args, **kwargs)


class Attendance(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField()
    is_present = models.BooleanField(default=True)
    marked_by = models.CharField(max_length=50, default='System')

    class Meta:
        unique_together = ['student', 'subject', 'date']

    def __str__(self):
        status = 'P' if self.is_present else 'A'
        return f"{self.student.name} | {self.subject.subject_code} | {self.date} | {status}"


class FacultyProfile(models.Model):
    """Links a staff/admin User to specific subjects they teach."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='facultyprofile')
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    department = models.CharField(max_length=100, default="Computer Science")
    designation = models.CharField(max_length=100, default="Assistant Professor")
    bio = models.TextField(blank=True)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='faculty')
    can_send_notices = models.BooleanField(default=True)
    can_enter_marks = models.BooleanField(default=True)
    can_upload_materials = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def class_pairs(self):
        return self.subjects.values("branch", "semester").distinct()


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    assigned_by = models.ForeignKey(FacultyProfile, on_delete=models.SET_NULL, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to="assignments/%Y/%m/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject.subject_code} - {self.title}"


class StudyMaterial(models.Model):
    MATERIAL_TYPES = [
        ("NOTE", "Note"),
        ("PDF", "PDF"),
        ("LINK", "Link"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="materials")
    uploaded_by = models.ForeignKey(FacultyProfile, on_delete=models.SET_NULL, null=True, blank=True)
    material_type = models.CharField(max_length=10, choices=MATERIAL_TYPES, default="NOTE")
    file = models.FileField(upload_to="materials/%Y/%m/", blank=True)
    external_link = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject.subject_code} - {self.title}"


class ClassSchedule(models.Model):
    WEEKDAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="schedules")
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.IntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.subject.subject_code} {self.get_weekday_display()} {self.start_time}"


class WebsiteVisit(models.Model):
    path = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    visited_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-visited_at"]

    def __str__(self):
        return f"{self.path} @ {self.visited_at:%Y-%m-%d %H:%M}"


class Notice(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(
        FacultyProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notices",
    )
    target_branches = models.CharField(max_length=50, blank=True,
                                       help_text="Comma-separated branch codes, e.g. CS,IT. Leave blank for all.")
    target_semesters = models.CharField(max_length=50, blank=True,
                                        help_text="Comma-separated semester numbers, e.g. 1,2,3. Leave blank for all.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def is_for_student(self, student):
        if self.target_branches:
            if student.branch not in [b.strip() for b in self.target_branches.split(',')]:
                return False
        if self.target_semesters:
            if str(student.semester) not in [s.strip() for s in self.target_semesters.split(',')]:
                return False
        return True


class CSVUpload(models.Model):
    """Track CSV uploads by Admin"""
    TYPE_STUDENTS = "STUDENTS"
    TYPE_SUBJECTS = "SUBJECTS"
    TYPE_INTERNAL_MARKS = "INTERNAL_MARKS"
    TYPE_RESULTS = "RESULTS"
    TYPE_ATTENDANCE = "ATTENDANCE"
    TYPE_NOTICES = "NOTICES"

    UPLOAD_TYPE_CHOICES = [
        (TYPE_STUDENTS, "Students (create/update)"),
        (TYPE_SUBJECTS, "Subjects (branch/semester wise)"),
        (TYPE_INTERNAL_MARKS, "Internal Marks (CA/MSE/Assignment)"),
        (TYPE_RESULTS, "Semester Results"),
        (TYPE_ATTENDANCE, "Attendance (per date)"),
        (TYPE_NOTICES, "Notices (target branch/semester)"),
    ]

    file = models.FileField(upload_to='csv_uploads/%Y/%m/')
    description = models.CharField(max_length=200)
    upload_type = models.CharField(max_length=30, choices=UPLOAD_TYPE_CHOICES, default=TYPE_STUDENTS)
    uploaded_by = models.CharField(max_length=100)
    upload_date = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    # Backward-compatible student counters
    students_created = models.IntegerField(default=0)
    students_updated = models.IntegerField(default=0)
    # Generic counters for any dataset type
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    errors = models.TextField(blank=True)

    class Meta:
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.description} ({self.upload_date.strftime('%Y-%m-%d %H:%M')})"
