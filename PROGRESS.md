# Progress

## Done
- Config cleanup: college name/logo/colors/contact ab env se (COLLEGE_NAME, COLLEGE_LOGO,
  PRIMARY_COLOR, COLLEGE_EMAIL, COLLEGE_PHONE + COLLEGE_ADDRESS/WEBSITE/AFFILIATION/
  ESTABLISHED/PRINCIPAL_NAME). Context processor + `templates/partials/college_colors.html`
  aur `college_logo.html` bane; GP Tekari naam/logo/colors code se hatae.

## In progress
- (kuch nahi)

## Next (is order mein karna ye hai)
1. Security fixes (SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSV validation)
2. Docker + Postgres + Caddy + deploy script (naya college add karne ka)
3. Tests likhna
4. views.py ko modules mein todna
5. WhatsApp/SMS alerts
6. Razorpay fee payment
7. Parent portal + reports
8. create_college management command

## Notes / decisions
- Branding sirf env se: `college_ums/settings.py` (COLLEGE_* + PRIMARY_COLOR) →
  `students/context_processors.py` → templates. Templates me koi college string nahi.
- `COLLEGE_LOGO` static path (`images/x.png`) ya full `https://` URL dono le sakta hai;
  blank = 🎓 icon fallback. `templates/partials/college_logo.html` handle karta hai.
- `PRIMARY_COLOR` `:root { --highlight, --table-header }` override karta hai
  (`templates/partials/college_colors.html`, har template me style.css ke baad include).
- Contact/website/affiliation/established/principal blank chhodne par template us block ko
  hide kar deta hai (koi dummy content nahi dikhta).
- `.env.example` poora documented hai; `render.yaml` + `docker-compose.yml` me bhi keys hain.
