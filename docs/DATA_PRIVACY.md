# Data Privacy — College UMS

Ye document batata hai ki student/parent/staff ka personal data **kahan** store hota hai,
**kaun** dekh sakta hai, kitne din rehta hai, aur erase/export kaise hota hai.
Kuch bhi code mein hardcoded nahi hai — college ka naam, contact aur retention period env se aate hain.

## 1. Kaunsa data kahan

| Data | Model / table | Bana kaise | Zaroori? |
|---|---|---|---|
| Naam, registration no. | `students_studentprofile.name`, `.registration_number` | CSV import / admin form | Haan |
| Phone | `students_studentprofile.phone` | optional (CSV se blank ho sakta hai) | **Nahi** |
| Email, address, parents' names, DOB | `students_studentprofile` (`email`, `address`, `father_name`, `mother_name`, `date_of_birth`) | admin form / student self-edit | **Nahi** (blank allowed) |
| Consent timestamp | `students_studentprofile.consent_given_at` | pehla successful login | Automatic |
| Attendance | `students_attendance` | teacher/admin bulk entry | Academic record |
| Internal marks | `students_internalexam` | teacher/admin entry | Academic record |
| Fees | `students_feestructure`, `students_feepayment` | admin entry | Financial record |
| Leave / feedback / doubts | `students_leaveapplication`, `students_feedback`, `students_doubt`, `students_doubtreply` | student submit | Student-generated |
| Notices / materials | `students_notice`, `students_studymaterial`, `students_assignment` | teacher/admin | Content |
| Logins, sessions | `auth_user` (hashed password), `django_session` | Django | Security |
| Page visits + IP | `students_websitevisit` | `WebsiteVisitMiddleware` | Security/usage |
| Audit trail | `students_auditlog` (user, action, object, IP, time) | admin/finance/marks actions | Accountability |
| Error reports | optional Sentry (`SENTRY_DSN`) | exceptions | Diagnostics — **PII redacted** |
| Backups | encrypted files in `backups/` (outside repo) | `scripts/backup_db.sh` | Disaster recovery |
| Uploads | `media/` (banners, assignments, study material) | teacher/admin upload | Content — type-checked |

Legal pages: `/privacy/` (`templates/privacy.html`) aur `/terms/` (`templates/terms.html`),
college ka naam/contact/retention years env se aate hain.

## 2. Kaun kya dekh sakta hai

| Role | Access |
|---|---|
| Student | Sirf apna profile, fees, marks, attendance, leave, feedback, doubts |
| Teacher | Apne assigned subjects ke students, unke marks/attendance, apni notices/materials |
| Admin (office) | College ke saare students, fees, marks, reports, imports — koi college-crossing nahi |
| Platform super admin | Sirf aggregate usage/health + support tickets; kisi college ka student data nahi (per-college DB) |
| Django `/admin/` | `is_staff` users only |

Permission matrix + tests: `docs/PERMISSIONS.md`, `students/tests/test_security.py`.
Har role-reversal (`student → admin page`, `teacher → student page`) test se blocked hai.

## 3. Data minimisation

- Phone **optional** hai (model `blank=True`; CSV mein bhi required nahi).
- `email`, `address`, `father_name`, `mother_name`, `date_of_birth` blank chhode ja sakte hain;
  templates blank hone par `-` ya block hide karte hain.
- Sirf wahi fields collect hote hain jo attendance/marks/fees/receipt ke liye chahiye.
- CSV import unknown columns ko ignore karta hai (store nahi karta).
- Login par sirf username (registration number) — email login optional nahi, isliye email
  personal field hai, mandatory nahi.

## 4. Logs, error pages aur Sentry

- `students/privacy.py` mein `redact_text()` + `RedactSensitiveFilter`:
  console logs se email, phone, aadhaar/card numbers, DOB, set-password tokens aur
  bearer tokens mask ho jate hain (`[email]`, `[phone]`, `[number]`, `[secret redacted]`).
- Sentry (agar `SENTRY_DSN` set hai): `send_default_pii=False`,
  `max_request_body_size='never'`, `before_send=scrub_sentry_event` — request body,
  cookies, query string, `user`, extra dict aur exception messages scrub hote hain.
- Custom `403/404/500` templates: koi traceback, settings ya SQL nahi dikhta.
- AI chat endpoint error par generic message deta hai (`str(e)` leak nahi).

## 5. Export / erase (data-subject requests)

Admin panel → Students → 🛡️ (Privacy tools):

1. **Export** — `/admin-panel/students/<id>/data-export/`: JSON download
   (profile, attendance, marks, fees, leave, feedback, doubts). `Cache-Control: no-store`,
   aur `AuditLog` mein `student.data_export` entry.
2. **Erase / anonymise** — `/admin-panel/students/<id>/anonymize/`: confirmation checkbox ke
   baad name/phone/email/address/parents/DOB erase, login band, username `anonymised-<id>`.
   Registration number, attendance, marks aur fee receipts **rehte hain** (academic/financial
   record), aur `AuditLog` mein `student.anonymize` entry banti hai.

Command line se bhi: `python manage.py purge_expired_data --apply` (neeche dekho).

## 6. Retention

| Setting | Default | Matlab |
|---|---|---|
| `DATA_RETENTION_YEARS` | 7 | itne saal baad student ka personal data anonymise |
| `AUDIT_LOG_RETENTION_DAYS` | 2555 (7y) | audit rows purge |
| `VISIT_RETENTION_DAYS` | 180 | page-visit rows purge |

`python manage.py purge_expired_data` (default **dry run**) eligible students aur purane
logs dikhata hai. `--apply` ke saath actual anonymise + purge karta hai; `--archive-dir`
dene par pehle academic JSON archive likhta hai.

Cron (monthly):

```cron
0 3 1 * * cd /opt/ums/<slug> && .venv/bin/python manage.py purge_expired_data --apply
```

## 7. Backups

- `scripts/backup_db.sh` — encrypted only (`BACKUP_ENCRYPTION_KEY`), 600 permissions,
  retention + integrity check.
- `scripts/restore_db.sh` — `--yes` ke bina restore nahi; round-trip actually test kiya gaya.
- Details aur tested evidence: `docs/BACKUP_RESTORE.md`.

## 8. Building blocks (code references)

| Kaam | File |
|---|---|
| Legal pages | `students/views/common.py:privacy_policy, terms_of_use`, `templates/public_page.html`, `privacy.html`, `terms.html` |
| Redaction | `students/privacy.py`, `students/logging_filters.py`, `settings.LOGGING` |
| Sentry scrubbing | `college_ums/settings.py` (`SENTRY_DSN` block) |
| Export / erase | `students/views/people.py:student_data_export, student_anonymize` |
| Retention job | `students/management/commands/purge_expired_data.py` |
| Backups | `scripts/backup_db.sh`, `scripts/restore_db.sh` |
| Tests | `students/tests/test_privacy.py` (23 tests) |

## 9. Kya abhi nahi hai (honest gaps)

- DPDP/GDPR ke liye formal **Data Processing Agreement** aur grievance officer contact
  template ke bahar hai — college ko publish karne se pehle ye review karna hoga.
- Parent portal abhi nahi bana (Phase 7), isliye parent ka access rule sirf student ke
  through hai.
- Media (assignments/material) abhi Caddy se serve hota hai, per-file access check nahi —
  graded content ke liye protected download chahiye (backlog).
- Mobile app/third-party integrations na hone se cross-border transfer question abhi nahi uthta.
