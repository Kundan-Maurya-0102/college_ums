# UX audit — admin / teacher / student walk

Method: `scripts/ux_audit.py` walks every GET route as each role (110 page renders),
then applies heuristics that map to real complaints. Findings were fixed and are now
locked by `students/tests/test_ux.py` (13 tests). Re-run any time:

```bash
.venv/bin/python scripts/ux_audit.py            # all roles
.venv/bin/python scripts/ux_audit.py --role student
```

## Findings → fixes

| # | Problem found | Pages affected | Fix | Guard |
|---|---|---|---|---|
| 1 | **No page heading** — 43 pages had no `<h1>`, so screen-reader users had no page title and the visual hierarchy started at `<h2>` | 43 app templates | one `<h1 class="page-title">` per page, generated from the existing page title | `test_every_app_template_has_one_h1`, `test_rendered_pages_have_one_h1` |
| 2 | **Silent validation failures** — 41 forms reloaded with red outlines but **no text** explaining what was wrong | notices, subjects, events, fees, marks, attendance, forms in student/teacher/forum | `partials/form_errors.html` summary (linked to each field) inserted in every form | `test_invalid_form_shows_errors_inline`, `test_every_form_template_shows_validation_errors` |
| 3 | **Mobile overflow** — fixed `grid-template-columns: 1fr 1fr` inline styles with no breakpoint (two side-by-side panes on a 360 px screen) | marks entry, CSV upload, notice form, subject form, student edit, profile edit, banners | `.grid-2` / `.grid-split` helpers that collapse at 900/1024 px, `min-width: 0` on children | `test_no_hardcoded_inline_multi_column_grids`, `test_grid_helpers_collapse_on_small_screens` |
| 4 | **Cryptic empty tables** — bare "No events." / "No payments recorded." with no next step | events, fee payments | `.empty-state` blocks with an icon, an explanation in the user's language and the next action | `test_list_templates_have_empty_states` |
| 5 | **Security/UX** — `target="_blank"` links without `rel="noopener"` (WhatsApp/Drive links) | students list, student dashboard, upload results, teacher content | `rel="noopener noreferrer"` everywhere | `test_blank_targets_are_noopener` |
| 6 | **Duplicate/odd headings** in printed certificates (4 × `<h1>` on one page) | certificates | document titles demoted to `<h2 class="cert-heading">`, page keeps one `<h1>` | same heading test |

## Already good (verified, not changed)

- toasts: `role="status"` + `aria-live="polite"`, auto-dismiss, manual close
- submit feedback: every submit button gets `.is-loading` + `aria-busy` (no double submits)
- tables: client-side search/sort/CSV export, mobile card view under 640 px with `data-label`
- destructive actions: confirm page or `data-confirm` on the button (no accidental deletes)
- filters keep their state across pagination (`{% query_transform %}`)
- pagination on all long lists (students, fees, admins, feedback, platform lists)
- skip link, breadcrumbs, focus-visible outlines, dark mode, offline page

## Known remaining gaps (deliberately deferred)

- Django's own `/admin/` change forms are not themed (labels exist, but the
  heuristic flags the filter sidebar); staff are pointed at the custom panel first.
- ~25 long inline `style` attributes remain on the dashboard/banners/attendance
  pages; they work and are responsive, but moving them into `theme.css` utility
  classes is queued in `BACKLOG.md`.
- No automated visual-diff screenshots (no headless browser on the build host);
  layout claims were verified by DOM/CSS assertions, not by pixel comparison.
