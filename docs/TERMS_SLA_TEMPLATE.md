# Terms of service & SLA — draft template

Replace every `[...]` before sending. This is a **template for discussion**, not legal
advice; have a lawyer review it for the college's state and jurisdiction.

---

## 1. Parties

- **Provider:** [Vendor legal name], [address], [GSTIN if applicable]
- **College:** [College legal name], [address], represented by [Principal/Registrar]
- **Effective date:** [DD Month YYYY]  **Term:** [12 months], renewable.

## 2. Service

1. The provider hosts and maintains the College UMS ("the Service") at
   `https://[college-domain]` for the college's internal academic administration.
2. **Per-college deployment.** The college's data lives in its own database and is not
   shared with any other college. No cross-college reporting exists.
3. Included modules: [students, attendance, marks & results, fees, notices & events,
   reports, staff/student/teacher panels].
4. Optional modules: [online fee payment, WhatsApp notifications, parent portal,
   AI assistant] — each enabled only when the college provides the required account
   (payment gateway / WhatsApp sender / API key) and pays the applicable fee.

## 3. Subscription and payment

| Plan | Limit | Fee (₹/month, excl. GST) |
|---|---|---|
| [Basic] | up to [500] students | [5,000] |
| [Pro] | up to [2,000] students | [9,000] |
| [Enterprise] | unlimited | [custom] |

- Billed [annually in advance / quarterly]. Invoices are raised on the [1st].
- Payment within [15] days. Late payment beyond [30] days may make the account
  **read-only** until cleared (data is never deleted for non-payment).
- Price revision: with [60] days' written notice, at renewal.

## 4. Data ownership and portability

1. **The college owns its data.** The provider processes it only to run the Service.
2. On request, and always within [30] days of termination, the provider delivers a full
   export (database dump + uploaded files) in an open format.
3. After [90] days from termination, the provider deletes the college's data and its
   backups, except records the provider must keep by law (invoices, tax records).
4. The college is the data controller for student data and is responsible for having a
   lawful basis (consent / legitimate use) and for its own privacy notice to students.
   The provider's privacy practices are described in `docs/DATA_PRIVACY.md`.

## 5. Service levels

| Metric | Commitment |
|---|---|
| Monthly uptime (excluding planned maintenance) | **99.5 %** |
| Planned maintenance window | Sundays [02:00–04:00 IST], notice ≥ 24 h |
| First response — critical (site down, data loss) | **2 business hours** |
| First response — high (a module unusable) | 8 business hours |
| First response — normal (question, small bug) | 2 business days |
| Critical issue workaround/resolution | target 8 business hours |
| Support channels | [phone], [email], in-app *Report a problem* |
| Support hours | Mon–Sat, [09:30–18:00 IST], excluding public holidays |
| Nightly backup | daily, encrypted, retained [30] days |
| Restore point objective (RPO) | 24 hours |
| Recovery time objective (RTO) | 8 business hours |

**Uptime credits:** if monthly uptime falls below the commitment, the college receives a
credit of [5 %] of that month's fee for each [1 %] shortfall, capped at [50 %] of the
monthly fee. Credits are applied to the next invoice and are the sole remedy for
availability shortfalls.

**Excluded from SLA:** outages caused by (a) the college's network, devices or DNS
changes, (b) third-party services the college supplies (payment gateway, WhatsApp
provider, email provider, SMS), (c) force majeure, (d) the college's own data errors,
(e) scheduled maintenance within the agreed window.

## 6. Responsibilities of the college

1. Provide accurate data and keep user lists current (leavers disabled promptly).
2. Keep admin credentials confidential; the provider may reset them on written request.
3. Do not upload unlawful content or attempt to breach the Service.
4. Nominate one coordinator who can raise and prioritise support requests.
5. Provide the third-party accounts/keys needed for optional modules.
6. Inform students and parents about the system and its privacy notice.

## 7. Security and confidentiality

1. The provider applies the controls in `SECURITY.md` (HTTPS, password hashing, role-based
   access, audit logging, encrypted backups, dependency scanning).
2. The provider notifies the college **without undue delay, and within 72 hours** of
   becoming aware of a personal-data breach affecting the college's data, with the facts
   known and the mitigation taken.
3. Staff of the provider access college data only for support, and only with the college's
   request or consent, except to prevent an active security incident.
4. Sub-processors (hosting, email, monitoring) are listed in `docs/OPERATIONS.md`;
   changes are notified [30] days in advance.

## 8. Changes to the Service

- Improvements and bug fixes may be deployed continuously; the college is notified of
  changes that alter workflows.
- Any change that removes a feature the college relies on requires [90] days' notice.

## 9. Termination

1. Either party may terminate for material breach with [30] days' written notice, if the
   breach is not cured.
2. The college may terminate at the end of a billing term with [30] days' notice; prepaid
   fees for the unused period are refunded pro-rata, excluding setup charges.
3. On termination: data export per section 4, then deletion.

## 10. Liability

1. The provider's total liability in any 12-month period is limited to the fees paid by
   the college in that period.
2. Neither party is liable for indirect or consequential loss, including lost admissions
   or lost academic time.
3. This limitation does not apply to wilful misconduct, or to a party's
   indemnity/confidentiality obligations.

## 11. Governing law

These terms are governed by the laws of India; courts at [district/city] have exclusive
jurisdiction.

---

## Signature

| Provider | College |
|---|---|
| Name: [ ] | Name: [ ] |
| Designation: [ ] | Designation: Principal / Registrar |
| Signature / date | Signature / date |
| Seal | Seal |

**Annexures:** (A) data-processing addendum if the college requires one,
(B) list of modules enabled, (C) fee schedule, (D) support contacts.
