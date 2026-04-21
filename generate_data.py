import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_ums.settings')
django.setup()

import csv
from students.models import StudentProfile, Subject, Attendance
from django.contrib.auth.models import User
import datetime
import random

def run():
    print("Reading CSV and creating students...")
    with open('test_student.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user, _ = User.objects.get_or_create(username=row['registration_number'])
            user.set_password('pass123')
            user.save()
            StudentProfile.objects.update_or_create(
                registration_number=row['registration_number'],
                defaults={
                    'user': user,
                    'name': row['name'],
                    'phone': row['phone'],
                    'email': row['email'],
                    'address': row['address'],
                    'branch': row['branch'],
                    'semester': int(row['semester']),
                    'year_of_admission': int(row['year_of_admission']),
                    'current_password': 'pass123',
                    'is_password_changed': True,
                }
            )

    print("Creating subjects...")
    # Make sure we have subjects for these branches/semesters
    for b in ['CS', 'IT', 'EC', 'ME', 'CE', 'EE']:
        for s in [2, 4, 6]:
            Subject.objects.get_or_create(branch=b, semester=s, subject_code=f'{b}{s}01', defaults={'subject_name': f'Core {b} Sem {s}'})

    print("Generating attendance for the last 5 days...")
    today = datetime.date.today()
    for i in range(5):
        d = today - datetime.timedelta(days=i)
        for student in StudentProfile.objects.all():
            subjects = Subject.objects.filter(branch=student.branch, semester=student.semester)
            for sub in subjects:
                Attendance.objects.update_or_create(
                    student=student, subject=sub, date=d,
                    defaults={'is_present': random.choice([True, True, True, False])} # 75% chance present
                )
    print("Done creating dummy data and attendance!")

if __name__ == '__main__':
    run()
