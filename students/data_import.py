import datetime
import pandas as pd

from django.db import transaction

from .csv_processor import normalize_columns, safe_date, safe_int, safe_str
from .models import Attendance, InternalExam, Notice, SemesterResult, StudentProfile, Subject


def _missing_required(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [c for c in required if c not in df.columns]


def _read_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return normalize_columns(df)


@transaction.atomic
def import_subjects(csv_path: str) -> dict:
    """
    Required columns:
      branch, semester, subject_code, subject_name
    Optional:
      credits, is_active
    """
    df = _read_csv(csv_path)
    required = ["branch", "semester", "subject_code", "subject_name"]
    missing = _missing_required(df, required)
    if missing:
        return {"created": 0, "updated": 0, "errors": [f"Missing columns: {', '.join(missing)}"], "rows": []}

    created = updated = 0
    errors: list[str] = []
    rows: list[dict] = []

    for i, r in df.iterrows():
        row_no = i + 2
        branch = safe_str(r.get("branch", "")).upper()
        sem = safe_int(r.get("semester"))
        code = safe_str(r.get("subject_code", "")).upper()
        name = safe_str(r.get("subject_name", ""))
        credits = safe_int(r.get("credits"), default=4) or 4
        is_active_raw = safe_str(r.get("is_active", "1")).lower()
        is_active = is_active_raw in ("1", "true", "yes", "y", "active")

        if not branch or not sem or not code or not name:
            msg = f"Row {row_no}: branch/semester/subject_code/subject_name required"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "key": f"{branch}-{sem}-{code}"})
            continue

        obj = Subject.objects.filter(branch=branch, semester=sem, subject_code=code).first()
        if obj:
            obj.subject_name = name
            obj.credits = credits
            obj.is_active = is_active
            obj.save()
            updated += 1
            rows.append({"row": row_no, "status": "updated", "message": "Subject updated", "key": f"{branch}-{sem}-{code}"})
        else:
            Subject.objects.create(
                branch=branch,
                semester=sem,
                subject_code=code,
                subject_name=name,
                credits=credits,
                is_active=is_active,
            )
            created += 1
            rows.append({"row": row_no, "status": "created", "message": "Subject created", "key": f"{branch}-{sem}-{code}"})

    return {"created": created, "updated": updated, "errors": errors, "rows": rows}


@transaction.atomic
def import_internal_marks(csv_path: str) -> dict:
    """
    Required columns:
      registration_number, subject_code, exam_type, marks_obtained, max_marks, exam_date
    Notes:
      - subject resolved by student's branch+semester + subject_code
      - upsert on (student, subject, exam_type)
    """
    df = _read_csv(csv_path)
    required = ["registration_number", "subject_code", "exam_type", "marks_obtained", "max_marks", "exam_date"]
    missing = _missing_required(df, required)
    if missing:
        return {"created": 0, "updated": 0, "errors": [f"Missing columns: {', '.join(missing)}"], "rows": []}

    created = updated = 0
    errors: list[str] = []
    rows: list[dict] = []

    for i, r in df.iterrows():
        row_no = i + 2
        reg = safe_str(r.get("registration_number", "")).upper()
        subject_code = safe_str(r.get("subject_code", "")).upper()
        exam_type = safe_str(r.get("exam_type", "")).upper()
        marks = safe_int(r.get("marks_obtained"))
        max_marks = safe_int(r.get("max_marks"))
        exam_date = safe_date(r.get("exam_date"))

        if not reg or not subject_code or not exam_type or marks is None or max_marks is None or not exam_date:
            msg = f"Row {row_no}: invalid/missing required fields"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        student = StudentProfile.objects.filter(registration_number=reg).select_related("user").first()
        if not student or not student.branch or not student.semester:
            msg = f"Row {row_no}: student not found or missing branch/semester ({reg})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        subject = Subject.objects.filter(branch=student.branch, semester=student.semester, subject_code=subject_code).first()
        if not subject:
            msg = f"Row {row_no}: subject not found for {student.branch} sem {student.semester} ({subject_code})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        obj = InternalExam.objects.filter(student=student, subject=subject, exam_type=exam_type).first()
        if obj:
            obj.marks_obtained = marks
            obj.max_marks = max_marks
            obj.exam_date = exam_date
            obj.save()
            updated += 1
            rows.append({"row": row_no, "status": "updated", "message": "Marks updated", "reg": reg})
        else:
            InternalExam.objects.create(
                student=student,
                subject=subject,
                exam_type=exam_type,
                marks_obtained=marks,
                max_marks=max_marks,
                exam_date=exam_date,
            )
            created += 1
            rows.append({"row": row_no, "status": "created", "message": "Marks created", "reg": reg})

    return {"created": created, "updated": updated, "errors": errors, "rows": rows}


@transaction.atomic
def import_results(csv_path: str) -> dict:
    """
    Required columns:
      registration_number, semester, subject_code, internal_marks, external_marks
    Notes:
      - subject resolved by student's branch + provided semester + subject_code
      - upsert on (student, semester, subject)
    """
    df = _read_csv(csv_path)
    required = ["registration_number", "semester", "subject_code", "internal_marks", "external_marks"]
    missing = _missing_required(df, required)
    if missing:
        return {"created": 0, "updated": 0, "errors": [f"Missing columns: {', '.join(missing)}"], "rows": []}

    created = updated = 0
    errors: list[str] = []
    rows: list[dict] = []

    for i, r in df.iterrows():
        row_no = i + 2
        reg = safe_str(r.get("registration_number", "")).upper()
        sem = safe_int(r.get("semester"))
        subject_code = safe_str(r.get("subject_code", "")).upper()
        internal = safe_int(r.get("internal_marks"), default=0) or 0
        external = safe_int(r.get("external_marks"), default=0) or 0

        if not reg or not sem or not subject_code:
            msg = f"Row {row_no}: registration_number/semester/subject_code required"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        student = StudentProfile.objects.filter(registration_number=reg).first()
        if not student or not student.branch:
            msg = f"Row {row_no}: student not found or missing branch ({reg})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        subject = Subject.objects.filter(branch=student.branch, semester=sem, subject_code=subject_code).first()
        if not subject:
            msg = f"Row {row_no}: subject not found for {student.branch} sem {sem} ({subject_code})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        obj = SemesterResult.objects.filter(student=student, semester=sem, subject=subject).first()
        if obj:
            obj.internal_marks = internal
            obj.external_marks = external
            obj.save()
            updated += 1
            rows.append({"row": row_no, "status": "updated", "message": "Result updated", "reg": reg})
        else:
            SemesterResult.objects.create(
                student=student,
                semester=sem,
                subject=subject,
                internal_marks=internal,
                external_marks=external,
            )
            created += 1
            rows.append({"row": row_no, "status": "created", "message": "Result created", "reg": reg})

    return {"created": created, "updated": updated, "errors": errors, "rows": rows}


@transaction.atomic
def import_attendance(csv_path: str) -> dict:
    """
    Required columns:
      registration_number, subject_code, date, is_present
    Optional:
      marked_by
    Notes:
      - subject resolved by student's branch+semester + subject_code
      - upsert on (student, subject, date)
    """
    df = _read_csv(csv_path)
    required = ["registration_number", "subject_code", "date", "is_present"]
    missing = _missing_required(df, required)
    if missing:
        return {"created": 0, "updated": 0, "errors": [f"Missing columns: {', '.join(missing)}"], "rows": []}

    created = updated = 0
    errors: list[str] = []
    rows: list[dict] = []

    for i, r in df.iterrows():
        row_no = i + 2
        reg = safe_str(r.get("registration_number", "")).upper()
        subject_code = safe_str(r.get("subject_code", "")).upper()
        date_val = safe_date(r.get("date"))
        is_present_raw = safe_str(r.get("is_present", "1")).lower()
        is_present = is_present_raw in ("1", "true", "yes", "y", "p", "present")
        marked_by = safe_str(r.get("marked_by", "CSV Import")) or "CSV Import"

        if not reg or not subject_code or not date_val:
            msg = f"Row {row_no}: registration_number/subject_code/date required"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        student = StudentProfile.objects.filter(registration_number=reg).first()
        if not student or not student.branch or not student.semester:
            msg = f"Row {row_no}: student not found or missing branch/semester ({reg})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        subject = Subject.objects.filter(branch=student.branch, semester=student.semester, subject_code=subject_code).first()
        if not subject:
            msg = f"Row {row_no}: subject not found for {student.branch} sem {student.semester} ({subject_code})"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg, "reg": reg})
            continue

        obj = Attendance.objects.filter(student=student, subject=subject, date=date_val).first()
        if obj:
            obj.is_present = is_present
            obj.marked_by = marked_by
            obj.save()
            updated += 1
            rows.append({"row": row_no, "status": "updated", "message": "Attendance updated", "reg": reg})
        else:
            Attendance.objects.create(
                student=student,
                subject=subject,
                date=date_val,
                is_present=is_present,
                marked_by=marked_by,
            )
            created += 1
            rows.append({"row": row_no, "status": "created", "message": "Attendance created", "reg": reg})

    return {"created": created, "updated": updated, "errors": errors, "rows": rows}


@transaction.atomic
def import_notices(csv_path: str) -> dict:
    """
    Required columns:
      title, content
    Optional:
      target_branches, target_semesters, is_active
    Notes:
      - creates notices; if `id` provided, updates that notice
    """
    df = _read_csv(csv_path)
    required = ["title", "content"]
    missing = _missing_required(df, required)
    if missing:
        return {"created": 0, "updated": 0, "errors": [f"Missing columns: {', '.join(missing)}"], "rows": []}

    created = updated = 0
    errors: list[str] = []
    rows: list[dict] = []

    for i, r in df.iterrows():
        row_no = i + 2
        notice_id = safe_int(r.get("id"))
        title = safe_str(r.get("title", ""))
        content = safe_str(r.get("content", ""))
        branches = safe_str(r.get("target_branches", ""))
        semesters = safe_str(r.get("target_semesters", ""))
        is_active_raw = safe_str(r.get("is_active", "1")).lower()
        is_active = is_active_raw in ("1", "true", "yes", "y", "active")

        if not title or not content:
            msg = f"Row {row_no}: title/content required"
            errors.append(msg)
            rows.append({"row": row_no, "status": "error", "message": msg})
            continue

        if notice_id:
            obj = Notice.objects.filter(pk=notice_id).first()
        else:
            obj = None

        if obj:
            obj.title = title
            obj.content = content
            obj.target_branches = branches
            obj.target_semesters = semesters
            obj.is_active = is_active
            obj.save()
            updated += 1
            rows.append({"row": row_no, "status": "updated", "message": f"Notice updated (id={obj.pk})"})
        else:
            obj = Notice.objects.create(
                title=title,
                content=content,
                target_branches=branches,
                target_semesters=semesters,
                is_active=is_active,
            )
            created += 1
            rows.append({"row": row_no, "status": "created", "message": f"Notice created (id={obj.pk})"})

    return {"created": created, "updated": updated, "errors": errors, "rows": rows}

