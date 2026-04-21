from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0003_remove_plaintext_password_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="csvupload",
            name="upload_type",
            field=models.CharField(
                choices=[
                    ("STUDENTS", "Students (create/update)"),
                    ("SUBJECTS", "Subjects (branch/semester wise)"),
                    ("INTERNAL_MARKS", "Internal Marks (CA/MSE/Assignment)"),
                    ("RESULTS", "Semester Results"),
                    ("ATTENDANCE", "Attendance (per date)"),
                    ("NOTICES", "Notices (target branch/semester)"),
                ],
                default="STUDENTS",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="csvupload",
            name="records_created",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="csvupload",
            name="records_updated",
            field=models.IntegerField(default=0),
        ),
    ]

