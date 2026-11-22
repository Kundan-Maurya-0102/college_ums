# Progress

## Done
- Config cleanup: college name/logo/colors/contact ab env se (COLLEGE_NAME, COLLEGE_LOGO,
  PRIMARY_COLOR, COLLEGE_EMAIL, COLLEGE_PHONE + COLLEGE_ADDRESS/WEBSITE/AFFILIATION/
  ESTABLISHED/PRINCIPAL_NAME). Context processor + `templates/partials/college_colors.html`
  aur `college_logo.html` bane; GP Tekari naam/logo/colors code se hatae.
- Security fixes: SECRET_KEY mandatory (no fallback), DEBUG default False,
  ALLOWED_HOSTS + CSRF_TRUSTED_ORIGINS env se, prod me secure cookies, set-password
  token expiry 48h, CSV upload type/size/content validation, seed passwords DEBUG-only.

## In progress
- (kuch nahi)

## Next (is order mein karna ye hai)
1. Docker + Postgres + Caddy + deploy script (naya college add karne ka)
2. Tests likhna
3. views.py ko modules mein todna
4. WhatsApp/SMS alerts
5. Razorpay fee payment
6. Parent portal + reports
7. create_college management command

## Notes / decisions
- Branding sirf env se: `college_ums/settings.py` (COLLEGE_* + PRIMARY_COLOR) →
  `students/context_processors.py` → templates. Templates me koi college string nahi.
- `COLLEGE_LOGO` static path (`images/x.png`) ya full `https://` URL dono le sakta hai;
  blank = 🎓 icon fallback. `templates/partials/college_logo.html` handle karta hai.
- `PRIMARY_COLOR` `:root { --highlight, --table-header }` override karta hai
  (`templates/partials/college_colors.html`, har template me style.css ke baad include).
- Contact/website/affiliation/established/principal blank chhodne par template us block ko
  hide kar deta hai (koi dummy content nahi dikhta).
- SECRET_KEY: env na ho to startup par `ImproperlyConfigured`; `DEBUG=False` + key
  `django-insecure...` se shuru ho to bhi refuse. Local `.env` me abhi ek dev key hai,
  isliye `DEBUG=False` par app boot nahi karega — deployment se pehle naya key generate karo
  (`python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`).
- ALLOWED_HOSTS ab strict hai: ad-hoc `django.test.Client()` ko `HTTP_HOST='localhost'`
  chahiye (test runner khud `testserver` add karta hai).
- CSV upload: `CSV_MAX_UPLOAD_MB` (default 5) + `.csv` extension + binary/UTF-8/csv.Sniffer
  check (`students/forms.py:CSVUploadForm.clean_file`).
- Set-password links: `PASSWORD_TOKEN_TIMEOUT_HOURS` (default 48) → `PASSWORD_RESET_TIMEOUT`.
- `generate_data.py` sirf `DEBUG=True` + `SEED_STUDENT_PASSWORD` set hone par chalta hai.
- `.env.example` poora documented hai; `render.yaml` + `docker-compose.yml` me bhi keys hain
  (compose ab SECRET_KEY shell/.env se leta hai, hardcoded "change-me" hata diya).
