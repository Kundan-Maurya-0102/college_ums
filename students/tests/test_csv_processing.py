"""CSV import processing tests: correct file, wrong header, duplicate, big file."""
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from students.models import CSVUpload, StudentProfile
from students.upload_router import process_any_csv_upload


class CSVProcessingTests(TestCase):
    """Test actual CSV import processing logic (beyond form validation)."""

    def _make_upload(self, content, media_root):
        return CSVUpload.objects.create(
            file=SimpleUploadedFile("students.csv", content),
            description="test",
            uploaded_by="admin",
            upload_type=CSVUpload.TYPE_STUDENTS,
        )

    def test_correct_csv_creates_students(self):
        """A well-formed CSV creates student profiles with unusable passwords."""
        with tempfile.TemporaryDirectory() as media_root, \
                override_settings(MEDIA_ROOT=media_root):
            content = (
                b"name,phone,registration_number,branch,semester\n"
                b"Asha Kumari,9876543210,CSV001,CS,1\n"
                b"Ravi Kumar,9876543211,CSV002,IT,2\n"
            )
            upload = self._make_upload(content, media_root)
            result = process_any_csv_upload(upload)

        self.assertEqual(result['created'], 2)
        self.assertEqual(result['errors'], [])
        self.assertTrue(StudentProfile.objects.filter(registration_number='CSV001').exists())
        self.assertTrue(StudentProfile.objects.filter(registration_number='CSV002').exists())
        # New students get unusable passwords
        for reg in ('CSV001', 'CSV002'):
            p = StudentProfile.objects.get(registration_number=reg)
            self.assertFalse(p.user.has_usable_password())

    def test_missing_required_header_returns_error(self):
        """CSV without 'name' or 'registration_number' column fails cleanly."""
        with tempfile.TemporaryDirectory() as media_root, \
                override_settings(MEDIA_ROOT=media_root):
            content = b"email,phone\ntest@example.com,9876543210\n"
            upload = self._make_upload(content, media_root)
            result = process_any_csv_upload(upload)

        self.assertEqual(result['created'], 0)
        self.assertTrue(any('missing required' in e.lower() for e in result['errors']))

    def test_duplicate_registration_number_updates(self):
        """Re-importing a reg number updates instead of duplicating."""
        existing_user = User.objects.create_user(username='csv_dup')
        StudentProfile.objects.create(
            user=existing_user, name='Old Name', phone='9000000000',
            registration_number='CSVDUP', branch='CS', semester=1,
        )
        with tempfile.TemporaryDirectory() as media_root, \
                override_settings(MEDIA_ROOT=media_root):
            content = b"name,phone,registration_number\nNew Name,9111111111,CSVDUP\n"
            upload = self._make_upload(content, media_root)
            result = process_any_csv_upload(upload)

        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['created'], 0)
        self.assertEqual(
            StudentProfile.objects.filter(registration_number='CSVDUP').count(), 1,
        )
        self.assertEqual(
            StudentProfile.objects.get(registration_number='CSVDUP').name, 'New Name',
        )

    def test_row_with_missing_name_reports_error(self):
        """A row missing the required 'name' field produces an error, not a crash."""
        with tempfile.TemporaryDirectory() as media_root, \
                override_settings(MEDIA_ROOT=media_root):
            content = b"name,registration_number\n,CSV_EMPTY\n"
            upload = self._make_upload(content, media_root)
            result = process_any_csv_upload(upload)

        self.assertEqual(result['created'], 0)
        self.assertTrue(len(result['errors']) > 0)

    def test_large_csv_processes_many_rows(self):
        """A CSV with many rows is processed without error."""
        with tempfile.TemporaryDirectory() as media_root, \
                override_settings(MEDIA_ROOT=media_root):
            header = b"name,phone,registration_number,branch,semester\n"
            rows = b"".join(
                f"Student {i},98765{i:05d},BIG{i:04d},CS,1\n".encode()
                for i in range(50)
            )
            upload = self._make_upload(header + rows, media_root)
            result = process_any_csv_upload(upload)

        self.assertEqual(result['created'], 50)
        self.assertEqual(result['errors'], [])
