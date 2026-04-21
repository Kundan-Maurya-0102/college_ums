from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0004_csvupload_upload_type_and_generic_counters"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studentprofile",
            name="branch",
            field=models.CharField(
                blank=True,
                choices=[
                    ("CS", "Computer Science"),
                    ("IT", "Information Technology"),
                    ("EC", "Electronics & Communication"),
                    ("ME", "Mechanical"),
                    ("CE", "Civil"),
                ],
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="subject",
            name="branch",
            field=models.CharField(
                choices=[
                    ("CS", "Computer Science"),
                    ("IT", "Information Technology"),
                    ("EC", "Electronics & Communication"),
                    ("ME", "Mechanical"),
                    ("CE", "Civil"),
                ],
                max_length=2,
            ),
        ),
    ]

