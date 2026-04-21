from django.db import transaction

from .csv_processor import process_csv_upload
from .data_import import (
    import_attendance,
    import_internal_marks,
    import_notices,
    import_results,
    import_subjects,
)
from .models import CSVUpload


@transaction.atomic
def process_any_csv_upload(upload: CSVUpload) -> dict:
    """
    Dispatch CSV processing based on upload_type.
    Returns unified dict: {created, updated, errors, rows}
    """
    if upload.upload_type == CSVUpload.TYPE_STUDENTS:
        return process_csv_upload(upload)
    if upload.upload_type == CSVUpload.TYPE_SUBJECTS:
        return import_subjects(upload.file.path)
    if upload.upload_type == CSVUpload.TYPE_INTERNAL_MARKS:
        return import_internal_marks(upload.file.path)
    if upload.upload_type == CSVUpload.TYPE_RESULTS:
        return import_results(upload.file.path)
    if upload.upload_type == CSVUpload.TYPE_ATTENDANCE:
        return import_attendance(upload.file.path)
    if upload.upload_type == CSVUpload.TYPE_NOTICES:
        return import_notices(upload.file.path)
    return {"created": 0, "updated": 0, "errors": [f"Unknown upload_type: {upload.upload_type}"], "rows": []}

