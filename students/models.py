from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class StudentProfile(models.Model):
    BRANCH_CHOICES = [
        ('CS', 'Computer Science'),
        ('IT', 'Information Technology'),
        ('CE', 'Civil'),
        ('EC', 'Electronics'),
        ('ME', 'Mechanical'),
        ('EE', 'Electrical'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # CSV Import Fields (Required)
    name = models.CharField(max_length=100)
    # Optional: only collected when the student/office provides it (data minimisation).
    phone = models.CharField(max_length=15, blank=True)
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
    # When the student accepted the privacy policy / terms (null = not recorded).
    consent_given_at = models.DateTimeField(null=True, blank=True)
    credentials_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["branch", "semester"], name="student_branch_sem_idx"),
            models.Index(fields=["-created_at"], name="student_created_idx"),
        ]

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

    def get_whatsapp_url(self, message=None):
        """Generates a direct WhatsApp (wa.me) link."""
        phone = self.phone.strip()
        # Clean phone number: remove non-digits
        import re
        clean_phone = re.sub(r'\D', '', phone)

        if len(clean_phone) == 10:
            clean_phone = f"91{clean_phone}"

        if not message:
            # Default message with set-password link
            from django.conf import settings
            link = self.get_set_password_link()
            college = getattr(settings, 'COLLEGE_NAME', '') or 'Student Portal'
            message = (
                f"🎓 *{college}*\n\n"
                f"Hello *{self.name}*,\n"
                f"Your student portal account is ready.\n\n"
                f"👤 *Username:* {self.registration_number.lower()}\n"
                f"🔑 *Set Password:* {link}\n\n"
                f"Please set your password and log in."
            )

        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        return f"https://wa.me/{clean_phone}?text={encoded_msg}"


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
        indexes = [
            models.Index(fields=["student", "subject"], name="iexam_student_subject_idx"),
            models.Index(fields=["exam_date"], name="iexam_date_idx"),
        ]

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
        indexes = [
            models.Index(fields=["date"], name="attendance_date_idx"),
            models.Index(fields=["subject", "date"], name="attendance_subject_date_idx"),
        ]

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
        indexes = [models.Index(fields=["-visited_at"], name="visit_time_idx")]

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
        indexes = [
            models.Index(fields=["is_active", "-created_at"], name="notice_active_idx"),
        ]

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


class BannerImage(models.Model):
    title = models.CharField(max_length=200, blank=True, help_text="Optional title for the banner")
    image = models.ImageField(upload_to="banners/")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Banner {self.id}"


class Doubt(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="doubts")
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class DoubtReply(models.Model):
    doubt = models.ForeignKey(Doubt, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.user.username} on {self.doubt.title}"


# ─────────────────── FEE MANAGEMENT ───────────────────

class FeeStructure(models.Model):
    FEE_TYPES = [
        ('TUITION', 'Tuition Fee'),
        ('EXAM', 'Examination Fee'),
        ('LAB', 'Laboratory Fee'),
        ('LIBRARY', 'Library Fee'),
        ('DEVELOPMENT', 'Development Fee'),
        ('OTHER', 'Other Fee'),
    ]

    branch = models.CharField(max_length=2, choices=StudentProfile.BRANCH_CHOICES)
    semester = models.IntegerField()
    fee_type = models.CharField(max_length=20, choices=FEE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    academic_year = models.CharField(max_length=9, help_text="e.g. 2024-2025")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['branch', 'semester', 'fee_type', 'academic_year']
        ordering = ['branch', 'semester', 'fee_type']

    def __str__(self):
        return f"{self.get_branch_display()} Sem-{self.semester} {self.get_fee_type_display()} ₹{self.amount}"

    def get_branch_display(self):
        return dict(StudentProfile.BRANCH_CHOICES).get(self.branch, self.branch)


class FeePayment(models.Model):
    PAYMENT_MODES = [
        ('CASH', 'Cash'),
        ('ONLINE', 'Online Transfer'),
        ('UPI', 'UPI'),
        ('DD', 'Demand Draft'),
        ('CHEQUE', 'Cheque'),
    ]
    STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial'),
        ('PENDING', 'Pending'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='fee_payments')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    receipt_number = models.CharField(max_length=50, unique=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODES, default='CASH')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PAID')
    remarks = models.TextField(blank=True)
    recorded_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=["status", "-payment_date"], name="feepayment_status_date_idx"),
            models.Index(fields=["payment_date"], name="feepayment_date_idx"),
            models.Index(fields=["student", "status"], name="feepayment_student_status_idx"),
        ]

    def __str__(self):
        return f"{self.student.name} — ₹{self.amount_paid} ({self.receipt_number})"


# ─────────────────── EXAM TIMETABLE ───────────────────

class ExamSchedule(models.Model):
    EXAM_TYPE_CHOICES = [
        ('MID_SEM', 'Mid Semester'),
        ('END_SEM', 'End Semester'),
        ('PRACTICAL', 'Practical'),
        ('VIVA', 'Viva'),
        ('BACKLOG', 'Backlog Exam'),
    ]

    branch = models.CharField(max_length=2, choices=StudentProfile.BRANCH_CHOICES)
    semester = models.IntegerField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exam_schedules')
    exam_type = models.CharField(max_length=15, choices=EXAM_TYPE_CHOICES)
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'start_time']

    def __str__(self):
        return f"{self.subject.subject_code} {self.get_exam_type_display()} — {self.exam_date}"


# ─────────────────── LEAVE APPLICATION ───────────────────

class LeaveApplication(models.Model):
    LEAVE_TYPES = [
        ('SICK', 'Sick Leave'),
        ('CASUAL', 'Casual Leave'),
        ('FAMILY', 'Family Emergency'),
        ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='leave_applications')
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPES)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leaves')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=["status"], name="leave_status_idx")]

    def __str__(self):
        return f"{self.student.name} — {self.get_leave_type_display()} ({self.from_date} to {self.to_date})"

    def duration_days(self):
        return (self.to_date - self.from_date).days + 1


# ─────────────────── FEEDBACK ───────────────────

class Feedback(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='feedbacks')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='feedbacks')
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks')
    rating = models.IntegerField(help_text="1 to 5")
    comments = models.TextField(blank=True)
    semester = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'subject', 'semester']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.name} → {self.subject.subject_code} ({self.rating}/5)"


# ─────────────────── EVENT / CALENDAR ───────────────────

class Event(models.Model):
    EVENT_TYPES = [
        ('HOLIDAY', 'Holiday'),
        ('EXAM', 'Examination'),
        ('FEST', 'Festival/Cultural'),
        ('WORKSHOP', 'Workshop/Seminar'),
        ('MEETING', 'Meeting'),
        ('OTHER', 'Other'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_date = models.DateField()
    event_type = models.CharField(max_length=15, choices=EVENT_TYPES, default='OTHER')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event_date']

    def __str__(self):
        return f"{self.title} ({self.event_date})"



class AuditLog(models.Model):
    """Who changed what, when (marks, fees, attendance, users, imports)."""

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="audit_entries")
    action = models.CharField(max_length=64)
    model_name = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"], name="audit_action_idx"),
            models.Index(fields=["user", "-created_at"], name="audit_user_idx"),
        ]

    def __str__(self):
        who = self.user.username if self.user else "system"
        return f"{who} {self.action} {self.model_name}:{self.object_id}".strip()


# ─────────────────── BUG / FEEDBACK REPORTS ───────────────────

class BugReport(models.Model):
    """In-app "report a problem" message from any signed-in user."""

    CATEGORIES = [
        ('BUG', 'Something is broken'),
        ('SLOW', 'Too slow / hangs'),
        ('CONFUSING', 'Hard to understand'),
        ('IDEA', 'Feature idea'),
        ('OTHER', 'Other'),
    ]
    STATUS = [
        ('OPEN', 'Open'),
        ('TRIAGED', 'Triaged'),
        ('FIXED', 'Fixed'),
        ('WONTFIX', "Won't fix"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, blank=True,
                            help_text="student / teacher / admin at the time of reporting")
    category = models.CharField(max_length=12, choices=CATEGORIES, default='BUG')
    message = models.TextField()
    page_url = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='OPEN')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'], name='bugreport_status_created_idx')]

    def __str__(self):
        return f"{self.get_category_display()} — {self.message[:40]}"
