"""Load a believable demo college so a new deployment can be shown in minutes.

    python manage.py seed_demo                 # 50 students, 8 teachers, idempotent
    python manage.py seed_demo --students 10   # smaller demo
    python manage.py seed_demo --flush         # wipe demo rows first

Everything is deterministic (fixed seed) and safe to re-run: it updates what it
created instead of duplicating. It refuses to run when DEBUG=False unless
--force is passed, so a real college can never get fake students by accident.
"""
import datetime
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from students.models import (
    Attendance,
    ClassSchedule,
    Event,
    ExamSchedule,
    FacultyProfile,
    FeePayment,
    FeeStructure,
    InternalExam,
    Notice,
    SemesterResult,
    StudentProfile,
    Subject,
)

User = get_user_model()

FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Reyansh', 'Krishna', 'Ishaan',
    'Ananya', 'Diya', 'Aadhya', 'Saanvi', 'Pari', 'Anika', 'Navya', 'Myra',
    'Rohan', 'Kabir', 'Yash', 'Neha', 'Priya', 'Sneha', 'Rahul', 'Manish',
    'Shreya', 'Kavya', 'Riya', 'Tanvi', 'Aman', 'Nitin', 'Pooja', 'Sakshi',
]
LAST_NAMES = [
    'Sharma', 'Verma', 'Gupta', 'Singh', 'Yadav', 'Kumar', 'Maurya', 'Prasad',
    'Mishra', 'Tiwari', 'Pandey', 'Chauhan', 'Khan', 'Ansari', 'Raj', 'Nair',
]
BRANCHES = ['CS', 'IT', 'CE', 'EC', 'ME', 'EE']
SUBJECT_NAMES = {
    'CS': [('CS301', 'Data Structures'), ('CS302', 'DBMS'), ('CS303', 'Operating Systems'),
           ('CS304', 'Computer Networks')],
    'IT': [('IT301', 'Web Technology'), ('IT302', 'Software Engineering'),
           ('IT303', 'Cloud Computing'), ('IT304', 'Cyber Security')],
    'CE': [('CE301', 'Surveying'), ('CE302', 'Structural Analysis'),
           ('CE303', 'Concrete Technology'), ('CE304', 'Fluid Mechanics')],
    'EC': [('EC301', 'Digital Electronics'), ('EC302', 'Signals & Systems'),
           ('EC303', 'Microprocessors'), ('EC304', 'Communication Systems')],
    'ME': [('ME301', 'Thermodynamics'), ('ME302', 'Machine Design'),
           ('ME303', 'Manufacturing Process'), ('ME304', 'Fluid Machinery')],
    'EE': [('EE301', 'Electrical Machines'), ('EE302', 'Power Systems'),
           ('EE303', 'Control Systems'), ('EE304', 'Measurements')],
}
FEE_TYPES = ['TUITION', 'EXAM', 'LIBRARY', 'DEVELOPMENT']
ACADEMIC_YEAR = '2025-2026'
DEMO_PASSWORD = 'Demo@12345'


class Command(BaseCommand):
    help = "Seed a demo college (students, teachers, subjects, attendance, marks, fees, notices)"

    def add_arguments(self, parser):
        parser.add_argument('--students', type=int, default=50)
        parser.add_argument('--teachers', type=int, default=8)
        parser.add_argument('--flush', action='store_true', help="delete demo rows before seeding")
        parser.add_argument('--force', action='store_true',
                            help="allow seeding while DEBUG=False (demo/staging only)")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError(
                "DEBUG=False: refusing to insert demo data. Use --force on a demo/staging box."
            )
        # Deterministic fake names for demo data; not used for tokens or passwords.
        rng = random.Random(20251124)  # nosec B311
        today = timezone.localdate()

        if options['flush']:
            self._flush()

        subjects = self._subjects()
        teachers = self._teachers(options['teachers'], subjects, rng)
        students = self._students(options['students'], rng)
        attendance = self._attendance(students, subjects, teachers, rng, today)
        marks = self._marks(students, subjects, rng, today)
        fees = self._fees(students, subjects, rng, today)
        notices = self._notices(teachers, today)
        self._events(today)
        self._timetable(subjects, teachers, rng)

        self.stdout.write(self.style.SUCCESS(
            f"Demo college ready: {len(students)} students, {len(teachers)} teachers, "
            f"{len(subjects)} subjects, {attendance} attendance rows, {marks} marks, "
            f"{fees} fee payments, {notices} notices. "
            f"Login: demo_student1 / {DEMO_PASSWORD} (staff: demo_teacher1)"
        ))

    # ── pieces ────────────────────────────────────────────────────────
    def _flush(self):
        StudentProfile.objects.filter(user__username__startswith='demo_').delete()
        User.objects.filter(username__startswith='demo_').delete()
        FacultyProfile.objects.filter(user__username__startswith='demo_').delete()
        Subject.objects.filter(subject_code__regex=r'^(CS|IT|CE|EC|ME|EE)30[1-4]$').delete()
        Notice.objects.filter(title__startswith='[Demo]').delete()
        Event.objects.filter(title__startswith='[Demo]').delete()
        FeeStructure.objects.filter(academic_year=ACADEMIC_YEAR,
                                    fee_type__in=FEE_TYPES).delete()
        self.stdout.write("demo rows removed")

    def _subjects(self):
        out = []
        for branch, subject_list in SUBJECT_NAMES.items():
            for code, name in subject_list:
                subject, _ = Subject.objects.update_or_create(
                    subject_code=code,
                    defaults=dict(branch=branch, semester=3, subject_name=name,
                                  credits=4, is_active=True),
                )
                out.append(subject)
        return out

    def _teachers(self, count, subjects, rng):
        profiles = []
        for i in range(1, count + 1):
            username = f'demo_teacher{i}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(email=f'{username}@example.edu', is_staff=True),
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=['password'])
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            profile, _ = FacultyProfile.objects.update_or_create(
                user=user,
                defaults=dict(name=name, email=f'{username}@example.edu',
                              phone=f'9{rng.randint(100000000, 999999999)}',
                              department='Engineering', is_active=True),
            )
            profile.subjects.set(rng.sample(subjects, 2))
            profiles.append(profile)
        return profiles

    def _students(self, count, rng):
        profiles = []
        year = 2023
        for i in range(1, count + 1):
            username = f'demo_student{i}'
            branch = BRANCHES[(i - 1) % len(BRANCHES)]
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=['password'])
            profile, _ = StudentProfile.objects.update_or_create(
                user=user,
                defaults=dict(
                    name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    registration_number=f'DEMO{i:04d}',
                    email=f'{username}@example.edu',
                    phone=f'8{rng.randint(100000000, 999999999)}',
                    branch=branch,
                    semester=3,
                    year_of_admission=year,
                    father_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    date_of_birth=datetime.date(2004, ((i % 12) + 1), ((i % 27) + 1)),
                    # demo logins skip the forced first-login password change
                    is_password_changed=True,
                ),
            )
            profiles.append(profile)
        return profiles

    def _attendance(self, students, subjects, teachers, rng, today):
        rows = 0
        for student in students:
            branch_subjects = [s for s in subjects if s.branch == student.branch][:2]
            for subject in branch_subjects:
                for day in range(20):
                    date = today - datetime.timedelta(days=day)
                    if date.weekday() >= 5:
                        continue
                    Attendance.objects.update_or_create(
                        student=student, subject=subject, date=date,
                        defaults=dict(is_present=rng.random() > 0.12,
                                      marked_by=rng.choice(teachers).name),
                    )
                    rows += 1
        return rows

    def _marks(self, students, subjects, rng, today):
        rows = 0
        for student in students:
            for subject in [s for s in subjects if s.branch == student.branch][:2]:
                for exam_type, max_marks in (('MID_TERM', 30), ('QUIZ', 20)):
                    InternalExam.objects.update_or_create(
                        student=student, subject=subject, exam_type=exam_type,
                        defaults=dict(marks_obtained=rng.randint(int(max_marks * 0.4), max_marks),
                                      max_marks=max_marks,
                                      exam_date=today - datetime.timedelta(days=30)),
                    )
                    rows += 1
                SemesterResult.objects.update_or_create(
                    student=student, subject=subject, semester=3,
                    defaults=dict(internal_marks=rng.randint(15, 30),
                                  external_marks=rng.randint(35, 70),
                                  total_marks=rng.randint(55, 98),
                                  grade=rng.choice(['A+', 'A', 'B+', 'B']),
                                  is_pass=True),
                )
        return rows

    def _fees(self, students, subjects, rng, today):
        structures = {}
        for branch in BRANCHES:
            for fee_type in FEE_TYPES:
                amount = {'TUITION': 15000, 'EXAM': 1500, 'LIBRARY': 800,
                          'DEVELOPMENT': 2500}[fee_type]
                structures[(branch, fee_type)], _ = FeeStructure.objects.update_or_create(
                    branch=branch, semester=3, fee_type=fee_type, academic_year=ACADEMIC_YEAR,
                    defaults=dict(amount=amount, is_active=True),
                )
        rows = 0
        for index, student in enumerate(students, start=1):
            structure = structures[(student.branch, 'TUITION')]
            status = 'PENDING' if index % 5 == 0 else ('PARTIAL' if index % 3 == 0 else 'PAID')
            paid = {'PAID': structure.amount,
                    'PARTIAL': structure.amount / 2,
                    'PENDING': 0}[status]
            if paid:
                FeePayment.objects.update_or_create(
                    receipt_number=f'DEMO-RCPT-{index:04d}',
                    defaults=dict(student=student, fee_structure=structure,
                                  amount_paid=paid,
                                  payment_date=today - datetime.timedelta(days=index % 40),
                                  payment_mode=rng.choice(['CASH', 'UPI', 'ONLINE']),
                                  status=status, recorded_by='Demo Admin'),
                )
                rows += 1
        return rows

    def _notices(self, teachers, today):
        author = teachers[0] if teachers else None
        texts = [
            ('[Demo] Mid-semester exam timetable released',
             'The mid-semester examination starts next Monday. Check the exam timetable page for '
             'subject-wise dates and rooms. Carry your identity card to every paper.'),
            ('[Demo] Scholarship forms due this Friday',
             'Students eligible for the state scholarship must submit the form to the office '
             'before Friday 5 PM. Late submissions will not be accepted.'),
            ('[Demo] Library timings extended during exams',
             'The reading room will stay open till 9 PM during the examination weeks. '
             'Bring your library card for entry.'),
        ]
        created = 0
        for title, content in texts:
            Notice.objects.update_or_create(
                title=title,
                defaults=dict(content=content, created_by=author, is_active=True),
            )
            created += 1
        return created

    def _events(self, today):
        events = [
            ('[Demo] Annual sports meet', 'FEST', today + datetime.timedelta(days=20)),
            ('[Demo] Industrial visit — BHEL', 'OTHER', today + datetime.timedelta(days=35)),
            ('[Demo] Parent-teacher meeting', 'MEETING', today + datetime.timedelta(days=10)),
        ]
        for title, event_type, date in events:
            Event.objects.update_or_create(
                title=title,
                defaults=dict(event_type=event_type, event_date=date, is_active=True),
            )

    def _timetable(self, subjects, teachers, rng):
        for subject in subjects[:12]:
            lecturer = next((t for t in teachers if subject in t.subjects.all()), teachers[0])
            ClassSchedule.objects.update_or_create(
                subject=subject, faculty=lecturer, weekday=(subject.id % 5) + 1,
                defaults=dict(start_time=datetime.time(10, 0), end_time=datetime.time(11, 0),
                              room=f'Room {100 + (subject.id % 20)}', is_active=True),
            )
            ExamSchedule.objects.update_or_create(
                subject=subject, exam_type='MID_SEM',
                defaults=dict(branch=subject.branch, semester=3,
                              exam_date=timezone.localdate() + datetime.timedelta(days=14),
                              start_time=datetime.time(10, 0), end_time=datetime.time(13, 0),
                              room='Hall A', is_active=True),
            )
