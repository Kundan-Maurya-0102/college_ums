# Multi-college isolation — what is guaranteed and how it is proven

Product model: **ek college = ek deployment** (apna domain, apna `.env`, apna
database, apna media folder). Ek hi codebase, N deployments.

## The guarantee

| Boundary | Rule | Why it holds |
|---|---|---|
| Database | Ek deployment me sirf `default` database hota hai | `IsolationBase` test: production settings me `DATABASES == ['default']` |
| Cross-DB reads | Koi view/model `.using(...)` se dusra DB nahi padhta | test scans `students/*.py` for `.using(` |
| Domain | Sirf college ka apna domain `ALLOWED_HOSTS` me hai; dusre college ka domain aane par 400 (view chalta hi nahi) | `DomainBoundaryTests` |
| Media | `/media/<path>` login ke baad, `realpath` guard; dusre deployment ki file us path par maujood hi nahi → 404 | `FileDownloadTests`, `students/views/media.py` |
| Data pages | List, detail, search, report, download — har page par dusre deployment ke markers ka `assertNotIn` | `CrossDeploymentPageTests`, `IdSwapTests` |
| CSV export | Sirf apne DB ki rows, valid CSV | `ExportTests` |
| Notifications | Mail/SMS/WhatsApp sirf diye gaye address par; koi broadcast nahi | `NotificationScopeTests`, `students/tasks.py` |
| Platform DB (shared) | Har college ka apna `metrics_token`; A ka token B ki row nahi likh sakta (constant-time compare, POST-only) | `PlatformBoundaryTests`, migration `platform_admin/0003` |

## Sabse ahem — ID badalne se kuch nahi hota

Isolation test me College B ki rows ko **jaan-boojh kar wahi primary keys** diye jaate
hain jo College A ki rows ki hain (`setUpTestData` dono DB me same order me data
banata hai, aur test assert karta hai `b_pk == a_pk`). Phir A ka user `?id=<B ka pk>`
kholta hai — jawaab me A ka hi data aata hai (`ACOLLEGE0001`, `RCPT-A`), B ka kuch
nahi. Kyunki B ka data doosre database me hai, "ID guess" karne se dusra college
khulta hi nahi.

## Kya jaan-boojh kar **nahi** kiya

Ek hi database me do college rakhna support nahi hai. Us model me har table par
`college_id` column chahiye hota (`django-tenants`/schema-per-tenant), warna har list
page leak ban jaata hai. Isliye:

- `create_college` ek deployment ke andar chalta hai, aur
- `DB_NAME`/`MEDIA_ROOT`/`SECRET_KEY` per deployment hote hain.

Agar kabhi "2 colleges, 1 database" chahiye ho, ye ek alag architecture decision
hai (`BACKLOG.md` me daalna), aur us waqt ye poora suite dobara likhna padega —
isliye us raaste par mat jaana bina test suite ke.

## Chalane ka tareeka

```bash
.venv/bin/python manage.py test students.tests.test_isolation -v 2
```

Test DB `college_b` sirf tests me banti hai (`settings.py` me `RUNNING_TESTS` guard),
production me koi doosri DB config hi nahi hoti — `test_production_settings_define_
exactly_one_database` isi ko pakadta hai.

## Naya college onboard karte waqt

1. `scripts/new_college.sh <slug>` → naya `.env` + compose project.
2 `manage.py create_college --name ... --slug ... --domain ...` → plan, College row,
   admin user, `metrics_token`.
3. Deployment ka domain us college ke `ALLOWED_HOSTS` me hi rakho.
4. `manage.py check_email you@college.edu` — notifications sach me ja rahi hain?
5. `students.tests.test_isolation` suite har release par chalti hai (CI me).
