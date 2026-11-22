# College UMS: Project Rules

## Project
Django 4.2 College Management System (app: `students`, Python 3.12).
Details: docs/PROJECT_REPORT.md

## Goal
Isko sellable product banana hai: ek hi codebase, har college ke liye alag deployment
(alag domain, alag DB, alag .env). Koi college-specific cheez code mein hardcoded nahi.

## Rules
- Ek baar mein sirf ek task karo. Chhote changes.
- Kaam shuru karne se pehle PROGRESS.md padho.
- Kaam ke baad PROGRESS.md update karo.
- Code badalne se pehle aur baad mein `python manage.py test` chalao.
- Secrets/keys kabhi code mein mat likho, sirf env variables.
- Migrations tod-fod mat karo, naya migration banao.
- Bade change se pehle 5-8 line ka plan batao.
- Har task ke baad git commit karo (clear message ke saath).

