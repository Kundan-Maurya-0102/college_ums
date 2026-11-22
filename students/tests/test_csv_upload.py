import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from students.forms import CSVUploadForm
from students.models import CSVUpload, StudentProfile
from students.upload_router import process_any_csv_upload


class CSVUploadFormTests(SimpleTestCase):
    def build_form(self, content, filename="data.csv"):
        upload = SimpleUploadedFile(filename, content)
        form = CSVUploadForm(
            data={"upload_type": CSVUpload.TYPE_STUDENTS, "description": "test"},
            files={"file": upload},
        )
        form.is_valid()
        return form

    def test_valid_csv_is_accepted(self):
        form = self.build_form(b"name,phone,registration_number\nAsha,9876543210,CS001\n")
        self.assertTrue(form.is_valid(), form.errors)

    def test_tab_separated_csv_with_bom_is_accepted(self):
        content = "name\tphone\tregistration_number\nAsha\t9876543210\tCS001\n".encode("utf-8-sig")
        form = self.build_form(content)
        self.assertTrue(form.is_valid(), form.errors)

    def test_wrong_extension_is_rejected(self):
        form = self.build_form(b"name,phone\nAsha,1\n", filename="data.txt")
        self.assertFalse(form.is_valid())
        self.assertIn("Only .csv files are allowed", str(form.errors["file"]))

    def test_binary_file_with_csv_name_is_rejected(self):
        form = self.build_form(b"\x00\x01\x02not really csv")
        self.assertFalse(form.is_valid())
        self.assertIn("binary", str(form.errors["file"]))

    def test_non_utf8_file_is_rejected(self):
        form = self.build_form(b"name,phone\n\xff\xfe,123\n")
        self.assertFalse(form.is_valid())
        self.assertIn("UTF-8", str(form.errors["file"]))

    def test_single_column_file_is_rejected(self):
        form = self.build_form(b"name\nAsha\n")
        self.assertFalse(form.is_valid())

    def test_size_limit_is_enforced_from_settings(self):
        with override_settings(CSV_MAX_UPLOAD_MB=0):
            upload = SimpleUploadedFile("data.csv", b"name,phone\nAsha,1\n")
            form = CSVUploadForm(
                data={"upload_type": CSVUpload.TYPE_STUDENTS, "description": "test"},
                files={"file": upload},
            )
            self.assertFalse(form.is_valid())
            self.assertIn("File size must be under 0 MB", str(form.errors["file"]))


class CSVImportTests(TestCase):
    def test_new_student_gets_unusable_password(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            content = b"name,phone,registration_number,branch,semester\nAsha Kumari,9876543210,CS001,CS,1\n"
            upload = CSVUpload.objects.create(
                file=SimpleUploadedFile("students.csv", content),
                description="CS sem 1",
                uploaded_by="admin",
                upload_type=CSVUpload.TYPE_STUDENTS,
            )

            result = process_any_csv_upload(upload)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 0)
        profile = StudentProfile.objects.get(registration_number="CS001")
        self.assertEqual(profile.name, "Asha Kumari")
        self.assertEqual(profile.user.username, "cs001")
        self.assertFalse(profile.user.has_usable_password())
        self.assertFalse(profile.is_password_changed)

    def test_existing_registration_number_is_updated_not_duplicated(self):
        existing_user = User.objects.create_user(username="cs002")
        StudentProfile.objects.create(
            user=existing_user,
            name="Old Name",
            phone="9000000000",
            registration_number="CS002",
            branch="CS",
            semester=1,
        )

        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            content = b"name,phone,registration_number\nNew Name,9111111111,CS002\n"
            upload = CSVUpload.objects.create(
                file=SimpleUploadedFile("students.csv", content),
                description="update",
                uploaded_by="admin",
                upload_type=CSVUpload.TYPE_STUDENTS,
            )
            result = process_any_csv_upload(upload)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(StudentProfile.objects.filter(registration_number="CS002").count(), 1)
        self.assertEqual(StudentProfile.objects.get(registration_number="CS002").name, "New Name")
