"""Генерація звітів: PDF (reportlab, з кирилицею) та Excel (openpyxl)."""
import io
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")


def _fmt(v):
    if isinstance(v, float) or v.__class__.__name__ == "Decimal":
        return f"{v:,.2f}".replace(",", " ")
    return "" if v is None else str(v)


def make_pdf(title, headers, rows, summary=None, col_widths=None):
    """Повертає PDF (bytes) з таблицею та блоком підсумків."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=28,
                            title=title)
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading1"], fontName="DejaVu-Bold", fontSize=18, textColor=colors.HexColor("#1f3a5f"))
    n = ParagraphStyle("n", parent=ss["Normal"], fontName="DejaVu", fontSize=9)
    cell = ParagraphStyle("c", parent=n, fontSize=8, leading=10)
    els = [Paragraph(title, h), Paragraph(f"ТехноМарт · сформовано {datetime.now():%d.%m.%Y %H:%M}", n), Spacer(1, 10)]
    hdr = ParagraphStyle("hc", parent=cell, textColor=colors.white)
    data = [[Paragraph(f"<b>{x}</b>", hdr) for x in headers]]
    data += [[Paragraph(_fmt(v).replace("&", "&amp;").replace("<", "&lt;"), cell) for v in r] for r in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    els.append(t)
    if summary:
        els.append(Spacer(1, 12))
        els.append(Paragraph("<br/>".join(f"<b>{k}:</b> {_fmt(v)}" for k, v in summary.items()), n))
    doc.build(els)
    return buf.getvalue()


def make_xlsx(sheet_title, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([float(v) if v.__class__.__name__ == "Decimal" else v for v in r])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value or "")) for c in col) + 3, 45)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
