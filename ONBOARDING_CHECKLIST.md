# User guide — College UMS

Step-by-step instructions for the four people who use the system every day.
Every screen name below is the label you actually see in the sidebar.

> Language: the **English / हिन्दी** selector sits in the top bar (and on the login
> page). It is remembered on that device. The **?** Help link next to it opens the
> short answers inside the app.

---

## 1. Office / Admin (Principal's office, clerk)

### 1.1 Log in
1. Open your college URL, e.g. `https://ums.yourcollege.ac.in`.
2. Enter your username and password → **Login**.
3. First time only: you land on **Change Password**. Set a new password (8+ characters).
   The old one stops working after that.

If you see *"Too many failed login attempts"*, wait 15 minutes or ask the platform
owner to restart the app — the counter is per device+IP.

### 1.2 Add students
**One student:** *All Students → ➕ Add student* → fill name, registration number,
branch, semester, year → **Save**. The login is created automatically with the
registration number as the username; the student sets their own password from the
set-password link you send (see *1.7*).

**A whole batch:** *CSV Upload* →
1. Download the sample file (the button below the upload box).
2. Keep the header row exactly as it is; one row per student.
3. Upload. The result page lists how many rows were created, updated or rejected,
   and **why** each rejected row failed (wrong branch code, duplicate registration
   number, missing name…).
4. Fix those rows and upload the same file again — nothing is duplicated: rows that
   already exist are updated, not re-created.

### 1.3 Attendance
*Take Attendance* → choose branch, semester, subject and date → every student appears
with a checkbox → clear/uncheck absentees → **Save**. Marking the same date again
updates it, it does not double-count.

*Manual Attendance* is for correcting a single student on a single date.

### 1.4 Marks and results
*Internal Marks* → exam, subject → type marks → **Save**.
*Results* shows total/grade/pass-fail per semester, with a CSV export for the exam cell.

### 1.5 Fees
1. *Fee Structure* → set the amount per branch + semester + fee type + academic year.
2. *Fee Payments → Add payment* → pick the student, the fee head, amount, mode
   (cash/UPI/online/DD/cheque) and date → **Save**. A receipt number is generated.
3. The list shows status **Paid / Partial / Pending**; filter by status to chase dues.

### 1.6 Notices and events
*Notices → Create* → title, content, target branches/semesters (blank = everyone) →
tick **Active** → **Save**. Students see it on their dashboard immediately.

*Events* is the calendar: holidays, exams, fests, meetings.

### 1.7 Reports and records
*Reports* → date range and branch filters → on-screen summary, CSV download.
*Upload History* keeps every CSV import with its error report.
*All Students → student → Privacy tools* exports everything stored about that student
or anonymises it (both are written to the audit log).
*Bug Reports* shows the messages users sent through the **Report a problem** button.

### 1.8 When something goes wrong
- A red box at the top of a form lists every field that needs fixing; click an item to
  jump to that box.
- Still stuck? Press the **Report a problem** button (bottom-right). The page address is
  attached automatically, so you do not have to describe where you were.

---

## 2. Teacher

### 2.1 Daily
1. Log in with the username the office gave you. First login → set your own password.
2. *Dashboard* shows your subjects, today's classes and pending work.

### 2.2 Attendance
*Attendance* → subject + date → mark → **Save**. It is written for the whole class at
once; you can correct it later the same way.

### 2.3 Marks
*Marks Entry* → exam → enter marks per student → **Save**. If you typed one mark wrong,
open the same exam again, correct it and save — the previous value is replaced.

### 2.4 Notes, assignments, notices
- *Notes / PDF*: upload a file or paste a link; students see it under their subject.
- *Assignments*: title, instructions, due date.
- *Notices*: write to your own classes (subject-wise), only if the office allowed it.

### 2.5 Students
*My Students* lists only the students you teach, with attendance % and last marks.

---

## 3. Student

### 3.1 First login
Use the registration number as username and the password the office gave you. The system
asks you to set your own password before anything else.

### 3.2 Dashboard
Shows your attendance %, fee status, latest notices and today's classes.

### 3.3 Fees
*My Fees* → what is paid, what is pending, receipt numbers and dates. It is a read-only
view: pay at the office, the clerk records it.

### 3.4 Exams
*Exam Schedule* → subject-wise dates, time and room.
*Certificates* → bonafide / character certificate and ID card, ready to print.

### 3.5 Requests
- *Leave Application*: pick type (sick/other), dates, reason → submit. The status
  (pending/approved/rejected) shows on the same page.
- *Feedback*: rate a subject and leave a comment. The office reads it, not other students.
- *Doubt Forum*: ask a question publicly; teachers and classmates can reply.

### 3.6 Profile
*Edit Profile* → phone, email, address. Your name, registration number and branch can
only be changed by the office. The phone number is optional — leave it blank if you do
not want to be contacted by SMS/WhatsApp.

---

## 4. Parent

The parent portal is **read-only** and is opened with a link/temporary password issued by
the office for a specific student. It shows:
- attendance summary (this month and overall),
- internal marks and results,
- fee dues and receipts,
- notices addressed to that student's branch/semester.

Parents cannot change any data. Ask the office for a fresh link if the old one expired.

---

## 5. Common questions

| Question | Answer |
|---|---|
| Password forgotten? | Ask the office for a **set-password link**; it expires in 48 hours. |
| Wrong branch/semester shown? | The office corrects it in *All Students*; a CSV re-upload with the same registration number also updates it. |
| Works on a phone? | Yes — the sidebar collapses, tables become cards, and the site can be added to the home screen. |
| No internet mid-work? | You get an offline page instead of an error; unsaved form data must be retyped. |
| Data export? | Every list has **Export CSV**; a student's full data can be exported by the office from *All Students → student → Privacy*. |
| Deleted something by mistake? | Deletions are permanent in the app; the office can restore from the previous nightly backup (see `docs/BACKUP_RESTORE.md`). |
