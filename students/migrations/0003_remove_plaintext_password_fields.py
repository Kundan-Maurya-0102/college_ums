from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0002_studentprofile_credentials_sent_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="studentprofile",
            name="auto_generated_password",
        ),
        migrations.RemoveField(
            model_name="studentprofile",
            name="current_password",
        ),
    ]

