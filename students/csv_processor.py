import logging
import random
import string
import pandas as pd
from django.contrib.auth.models import User
from django.db import transaction

from .models import CSVUpload, StudentProfile
from .password_links import build_set_password_link

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['name', 'phone', 'registration_number']
OPTIONAL_COLUMNS = ['email', 'branch', 'semester', 'year_of_admission',
                    'father_name', 'mother_name', 'address', 'date_of_birth']

VALID_BRANCHES = ['CS', 'IT', 'EC', 'ME', 'CE']


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to lowercase and strip whitespace."""
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    return df


def validate_row(row: dict, row_num: int) -> list:
    """Validate a single CSV row. Returns list of error strings."""
    errors = []
    for col in REQUIRED_COLUMNS:
        val = row.get(col, '')
        if pd.isna(val) or str(val).strip() == '':
            errors.append(f"Row {row_num}: Missing required field '{col}'")

    phone = str(row.get('phone', '')).strip()
    if phone and not phone.replace('+', '').replace('-', '').isdigit():
        errors.append(f"Row {row_num}: Invalid phone number '{phone}'")

    branch = str(row.get('branch', '')).strip().upper()
    if branch and branch not in VALID_BRANCHES:
        errors.append(f"Row {row_num}: Invalid branch '{branch}' (valid: {', '.join(VALID_BRANCHES)})")

    semester = row.get('semester', '')
    if semester and not pd.isna(semester):
        try:
            s = int(semester)
            if not (1 <= s <= 6):
                errors.append(f"Row {row_num}: Semester must be 1-6, got {s}")
        except (ValueError, TypeError):
            errors.append(f"Row {row_num}: Invalid semester '{semester}'")

    return errors


def safe_str(val, default='') -> str:
    if pd.isna(val):
        return default
    return str(val).strip()


def safe_int(val, default=None):
    try:
        if pd.isna(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_date(val):
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


@transaction.atomic
def process_csv_upload(csv_upload: CSVUpload) -> dict:
    """
    Main CSV processing function.
    Returns: {'created': int, 'updated': int, 'errors': list, 'rows': list}
    """
    created_count = 0
    updated_count = 0
    all_errors = []
    row_results = []  # For display in UI

    try:
        df = pd.read_csv(csv_upload.file.path)
    except Exception as e:
        error = f"Failed to read CSV file: {e}"
        csv_upload.errors = error
        csv_upload.is_processed = True
        csv_upload.save()
        return {'created': 0, 'updated': 0, 'errors': [error], 'rows': []}

    df = normalize_columns(df)

    # Check required columns exist
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        error = f"CSV missing required columns: {', '.join(missing_cols)}"
        csv_upload.errors = error
        csv_upload.is_processed = True
        csv_upload.save()
        return {'created': 0, 'updated': 0, 'errors': [error], 'rows': []}

    for row_num, row in df.iterrows():
        actual_row = row_num + 2  # 1-indexed + header
        row_dict = row.to_dict()

        errors = validate_row(row_dict, actual_row)
        if errors:
            all_errors.extend(errors)
            row_results.append({
                'row': actual_row,
                'name': safe_str(row_dict.get('name', '')),
                'reg': safe_str(row_dict.get('registration_number', '')),
                'status': 'error',
                'message': ' | '.join(errors),
            })
            continue

        reg_no = safe_str(row_dict.get('registration_number')).upper()
        name = safe_str(row_dict.get('name'))
        phone = safe_str(row_dict.get('phone'))
        email = safe_str(row_dict.get('email'))
        branch = safe_str(row_dict.get('branch', '')).upper()
        semester = safe_int(row_dict.get('semester'))
        year_of_admission = safe_int(row_dict.get('year_of_admission'))
        father_name = safe_str(row_dict.get('father_name'))
        mother_name = safe_str(row_dict.get('mother_name'))
        address = safe_str(row_dict.get('address'))
        dob = safe_date(row_dict.get('date_of_birth'))

        existing_profile = StudentProfile.objects.filter(registration_number=reg_no).first()

        if existing_profile:
            # UPDATE existing student
            existing_profile.name = name
            existing_profile.phone = phone
            if email:
                existing_profile.email = email
            if branch:
                existing_profile.branch = branch
            if semester:
                existing_profile.semester = semester
            if year_of_admission:
                existing_profile.year_of_admission = year_of_admission
            if father_name:
                existing_profile.father_name = father_name
            if mother_name:
                existing_profile.mother_name = mother_name
            if address:
                existing_profile.address = address
            if dob:
                existing_profile.date_of_birth = dob
            existing_profile.save()
            updated_count += 1
            row_results.append({
                'row': actual_row,
                'name': name,
                'reg': reg_no,
                'status': 'updated',
                'message': 'Student record updated successfully.',
            })
        else:
            # CREATE new student
            username = reg_no.lower()

            # Ensure unique username
            if User.objects.filter(username=username).exists():
                username = f"{username}_{phone[-4:]}"

            user = User.objects.create_user(
                username=username,
                first_name=name.split()[0] if name else '',
                last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
                email=email,
            )
            # Student must set password using a secure one-time link
            user.set_unusable_password()
            user.save()

            profile = StudentProfile.objects.create(
                user=user,
                name=name,
                phone=phone,
                registration_number=reg_no,
                email=email,
                branch=branch,
                semester=semester,
                year_of_admission=year_of_admission,
                father_name=father_name,
                mother_name=mother_name,
                address=address,
                date_of_birth=dob,
            )

            created_count += 1
            set_password_link = build_set_password_link(user)
            row_results.append({
                'row': actual_row,
                'name': name,
                'reg': reg_no,
                'status': 'created',
                'message': "Created. Share set-password link with student.",
                'set_password_link': set_password_link,
            })

    # Save summary to CSVUpload record
    csv_upload.is_processed = True
    csv_upload.students_created = created_count
    csv_upload.students_updated = updated_count
    csv_upload.errors = '\n'.join(all_errors)
    csv_upload.save()

    return {
        'created': created_count,
        'updated': updated_count,
        'errors': all_errors,
        'rows': row_results,
    }
