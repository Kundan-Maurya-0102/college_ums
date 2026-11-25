"""Branded PDF documents (hall ticket, marksheet) built with reportlab.

Everything visible comes from settings/env, so a deployment prints its own letterhead:
  COLLEGE_NAME, COLLEGE_ADDRESS, COLLEGE_AFFILIATION, COLLEGE_ESTABLISHED,
  COLLEGE_LOGO (static path or absolute URL), PRIMARY_COLOR (also the table header).
No student data is ever written to disk: the PDF is produced in memory per request.

Photographs and QR codes are optional — if Pillow/reportlab cannot read the photo, or a
QR cannot be built, the document still prints (a blank box / the code as text).
"""
import io
import logging
from datetime import date

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


# ── branding helpers ─────────────────────────────────────────────────────
def brand_colour():
    """The college's PRIMARY_COLOR (falls back to a safe blue)."""
    raw = (getattr(settings, 'PRIMARY_COLOR', '') or '#1d4ed8').strip()
    try:
        return colors.HexColor(raw if raw.startswith('#') else f'#{raw}')
    except Exception:  # noqa: BLE001 - a broken env value must not break a document
        return colors.HexColor('#1d4ed8')


def _logo_path():
    """Resolve COLLEGE_LOGO to a local file reportlab can open, or None."""
    import os

    logo = (getattr(settings, 'COLLEGE_LOGO', '') or '').strip()
    if not logo or logo.startswith(('http://', 'https://')):
        return None            # remote logos are not fetched while printing
    base = os.path.join(settings.BASE_DIR, 'static')
    candidate = os.path.join(base, logo.lstrip('/'))
    return candidate if os.path.isfile(candidate) else None


def _styles():
    sheet = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('T', parent=sheet['Heading1'], fontSize=16, leading=19,
                                alignment=1, spaceAfter=2),
        'sub': ParagraphStyle('S', parent=sheet['Normal'], fontSize=8.5, leading=11,
                              alignment=1, textColor=colors.HexColor('#475569')),
        'doc': ParagraphStyle('D', parent=sheet['Heading2'], fontSize=11.5, leading=14,
                              alignment=1, spaceBefore=6, spaceAfter=6),
        'body': ParagraphStyle('B', parent=sheet['Normal'], fontSize=9, leading=12),
        'small': ParagraphStyle('s', parent=sheet['Normal'], fontSize=7.6, leading=10),
        'cell': ParagraphStyle('C', parent=sheet['Normal'], fontSize=8.4, leading=10),
        'label': ParagraphStyle('L', parent=sheet['Normal'], fontSize=8.4, leading=10,
                                textColor=colors.HexColor('#475569')),
    }


def letterhead(styles):
    """Logo + college identity block, reused by both document types."""
    name = getattr(settings, 'COLLEGE_NAME', '') or 'College'
    address = getattr(settings, 'COLLEGE_ADDRESS', '') or ''
    affiliation = getattr(settings, 'COLLEGE_AFFILIATION', '') or ''
    established = getattr(settings, 'COLLEGE_ESTABLISHED', '') or ''

    text_column = [Paragraph(name, styles['title'])]
    if address:
        text_column.append(Paragraph(address, styles['sub']))
    extra = ' · '.join(part for part in (
        f'Affiliated to {affiliation}' if affiliation else '',
        f'Established {established}' if established else '',
    ) if part)
    if extra:
        text_column.append(Paragraph(extra, styles['sub']))

    logo_path = _logo_path()
    if logo_path:
        try:
            cell = Image(logo_path, width=18 * mm, height=18 * mm, kind='proportional')
            table = Table([[cell, text_column]], colWidths=[22 * mm, None])
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            return table
        except Exception:  # noqa: BLE001 - bad image file, print without it
            logger.warning('college logo could not be embedded in the PDF')
    return KeepTogether(text_column)


def _footer(canvas, doc, extra=''):
    canvas.saveState()
    colour = brand_colour()
    width, _height = A4
    canvas.setStrokeColor(colour)
    canvas.setLineWidth(0.8)
    canvas.line(15 * mm, 16 * mm, width - 15 * mm, 16 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor('#64748b'))
    name = getattr(settings, 'COLLEGE_NAME', '') or 'College'
    left = f'{name} · computer generated document'
    canvas.drawString(15 * mm, 11 * mm, left[:110])
    if extra:
        canvas.drawRightString(width - 15 * mm, 11 * mm, extra[:80])
    canvas.drawRightString(width - 15 * mm, 6.5 * mm, f'page {doc.page}')
    canvas.restoreState()


def _qr_image(text, size=26 * mm):
    """QR for the verification URL. Returns None when qrcode/Pillow are unavailable."""
    try:
        import qrcode
    except ImportError:  # optional dependency
        return None
    try:
        qr = qrcode.QRCode(box_size=10, border=1)
        qr.add_data(text)
        qr.make(fit=True)
        buffer = io.BytesIO()
        qr.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
        buffer.seek(0)
        return Image(buffer, width=size, height=size)
    except Exception:  # noqa: BLE001 - never block a document on a QR code
        logger.warning('QR code could not be generated')
        return None


def _photo_flowable(profile, styles, size=24 * mm):
    """Student photo when one was uploaded and is readable."""
    photo = getattr(profile, 'photo', None)
    if not photo:
        return None
    try:
        path = photo.path
        return Image(path, width=size, height=size * 1.2, kind='proportional')
    except Exception:  # noqa: BLE001 - missing file or unreadable image
        return None


def _brand_table(rows, col_widths, header=True):
    table = Table(rows, colWidths=col_widths)
    style = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ('BACKGROUND', (0, 0), (-1, 0), brand_colour()),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]
    table.setStyle(TableStyle(style))
    return table


# ── documents ────────────────────────────────────────────────────────────
def hall_ticket_pdf(data):
    """`data` comes from students.exams.hall_ticket_data()."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=14 * mm, bottomMargin=20 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f"Hall ticket — {data['student'].registration_number}",
                            author=getattr(settings, 'COLLEGE_NAME', '') or 'College UMS')
    flow = [letterhead(styles),
            Paragraph('HALL TICKET', styles['doc']),
            Paragraph(f"{data['exam_label']} · Semester {data['semester']} · "
                      f"Academic year {data['academic_year']}", styles['sub']),
            Spacer(1, 6)]

    photo = _photo_flowable(data['student'], styles)
    identity = [
        [Paragraph('<b>Name</b>', styles['label']),
         Paragraph(data['student'].name, styles['cell']),
         Paragraph('<b>Registration No.</b>', styles['label']),
         Paragraph(data['student'].registration_number, styles['cell'])],
        [Paragraph('<b>Branch</b>', styles['label']),
         Paragraph(data['student'].get_branch_display_name() or '—', styles['cell']),
         Paragraph('<b>Semester</b>', styles['label']),
         Paragraph(str(data['semester'] or '—'), styles['cell'])],
        [Paragraph('<b>Father / Guardian</b>', styles['label']),
         Paragraph(data['student'].father_name or '—', styles['cell']),
         Paragraph('<b>Issued on</b>', styles['label']),
         Paragraph(data['issued_on'].strftime('%d %b %Y'), styles['cell'])],
    ]
    if photo:
        identity_row = Table([[photo, _brand_table(identity, [26 * mm, 60 * mm, 32 * mm, None],
                                                   header=False)]],
                             colWidths=[30 * mm, None])
        identity_row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                          ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        flow.append(identity_row)
    else:
        flow.append(_brand_table(identity, [30 * mm, 60 * mm, 32 * mm, None], header=False))

    flow.append(Spacer(1, 8))
    flow.append(Paragraph('Examination schedule', styles['body']))
    rows = [['Date', 'Day', 'Subject', 'Time', 'Room']]
    for exam in data['exams']:
        rows.append([
            exam.exam_date.strftime('%d %b %Y'),
            exam.exam_date.strftime('%a'),
            f'{exam.subject.subject_code} — {exam.subject.subject_name}',
            f'{exam.start_time.strftime("%H:%M")}–{exam.end_time.strftime("%H:%M")}',
            exam.room or '—',
        ])
    if len(rows) == 1:
        rows.append(['—', '—', 'No exams scheduled yet — contact the exam cell', '—', '—'])
    flow.append(_brand_table(rows, [22 * mm, 14 * mm, None, 30 * mm, 18 * mm]))

    flow.append(Spacer(1, 8))
    instructions = data['instructions']
    flow.append(Paragraph('Instructions', styles['body']))
    for index, line in enumerate(instructions, start=1):
        flow.append(Paragraph(f'{index}. {line}', styles['small']))

    # verification block: QR plus the human-readable code
    verify_url = data['verify_url']
    qr = _qr_image(verify_url)
    code_para = Paragraph(
        f'<b>Verification code:</b> {data["verification_code"]}<br/>'
        f'Check at: {verify_url}<br/><br/>'
        'This ticket is valid only with a photo ID and the verification code above. '
        'Anyone can confirm it was issued by this college; no personal marks are shown '
        'on the verification page.', styles['small'])
    if qr:
        block = Table([[qr, code_para]], colWidths=[30 * mm, None])
    else:
        block = Table([[code_para]], colWidths=[None])
    block.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                               ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
                               ('LEFTPADDING', (0, 0), (-1, -1), 6)]))
    flow += [Spacer(1, 10), block, Spacer(1, 14),
             Paragraph('_____________________________<br/>Controller of Examinations', styles['body'])]

    doc.build(flow, onFirstPage=lambda canvas, d: _footer(
        canvas, d, f'hall ticket · {data["student"].registration_number}'),
        onLaterPages=lambda canvas, d: _footer(canvas, d))
    return buffer.getvalue()


def marksheet_pdf(data):
    """`data` comes from students.exams.marksheet_data()."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=14 * mm, bottomMargin=20 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f"Marksheet — {data['student'].registration_number}",
                            author=getattr(settings, 'COLLEGE_NAME', '') or 'College UMS')
    flow = [letterhead(styles),
            Paragraph('CONSOLIDATED MARKSHEET', styles['doc']),
            Paragraph(f"Semester {data['semester']} · Academic year {data['academic_year']}",
                      styles['sub']),
            Spacer(1, 6)]

    identity = [
        [Paragraph('<b>Name</b>', styles['label']),
         Paragraph(data['student'].name, styles['cell']),
         Paragraph('<b>Registration No.</b>', styles['label']),
         Paragraph(data['student'].registration_number, styles['cell'])],
        [Paragraph('<b>Branch</b>', styles['label']),
         Paragraph(data['student'].get_branch_display_name() or '—', styles['cell']),
         Paragraph('<b>Semester</b>', styles['label']),
         Paragraph(str(data['semester']), styles['cell'])],
    ]
    flow.append(_brand_table(identity, [30 * mm, 60 * mm, 32 * mm, None], header=False))

    flow.append(Spacer(1, 8))
    rows = [['Code', 'Subject', 'Credits', 'Internal', 'External', 'Total', 'Grade', 'Result']]
    for row in data['subjects']:
        rows.append([
            row['code'], row['name'], str(row['credits']),
            str(row['internal']), str(row['external']), str(row['total']),
            row['grade'] or '—', 'Pass' if row['is_pass'] else 'Fail',
        ])
    if len(rows) == 1:
        rows.append(['—', 'No results published for this semester', '—', '—', '—', '—', '—', '—'])
    flow.append(_brand_table(rows, [18 * mm, None, 16 * mm, 18 * mm, 18 * mm, 16 * mm, 14 * mm, 16 * mm]))

    flow.append(Spacer(1, 8))
    summary = [
        ['Credits registered', str(data['credits_total'])],
        ['Credits earned', str(data['credits_earned'])],
        ['SGPA', f"{data['sgpa']:.2f}" if data['sgpa'] is not None else '—'],
        ['CGPA', f"{data['cgpa']:.2f}" if data['cgpa'] is not None else '—'],
        ['Result', data['result']],
    ]
    flow.append(_brand_table(summary, [60 * mm, None], header=False))

    if data['backlogs']:
        flow.append(Spacer(1, 8))
        flow.append(Paragraph('<b>Backlogs to clear</b>', styles['body']))
        backlog_rows = [['Code', 'Subject', 'Marks', 'Grade']]
        for row in data['backlogs']:
            backlog_rows.append([row['code'], row['name'], str(row['total']), row['grade']])
        flow.append(_brand_table(backlog_rows, [20 * mm, None, 24 * mm, 20 * mm]))

    flow.append(Spacer(1, 12))
    qr = _qr_image(data['verify_url'])
    note = Paragraph(
        f'<b>Verification code:</b> {data["verification_code"]}<br/>'
        f'Check at: {data["verify_url"]}<br/><br/>'
        'Grade points: O 10, A+ 9, A 8, B+ 7, B 6, C 5, F 0. '
        'SGPA = Σ(credits × grade points) / Σ credits for this semester; '
        'CGPA uses every published semester.', styles['small'])
    block = Table([[qr, note]] if qr else [[note]],
                  colWidths=[30 * mm, None] if qr else [None])
    block.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                               ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
                               ('LEFTPADDING', (0, 0), (-1, -1), 6)]))
    flow += [block, Spacer(1, 14),
             Paragraph('_____________________________<br/>Controller of Examinations<br/>'
                       f'Issued on {data["issued_on"].strftime("%d %b %Y")}', styles['body'])]

    doc.build(flow, onFirstPage=lambda canvas, d: _footer(
        canvas, d, f'marksheet · {data["student"].registration_number}'),
        onLaterPages=lambda canvas, d: _footer(canvas, d))
    return buffer.getvalue()


def today():
    return date.today()
