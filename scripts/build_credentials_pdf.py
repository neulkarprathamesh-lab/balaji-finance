"""Build a colourful A4 credentials PDF for Balaji FeeHub with the school logo."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

APP = Path("/app")
LOGO = APP / "frontend" / "public" / "school-logo.jpeg"
OUT_DIR = APP / "frontend" / "public" / "downloads"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "BalajiFeeHub-Credentials.pdf"

# Brand palette
AMBER      = colors.HexColor("#F59E0B")
AMBER_DARK = colors.HexColor("#B45309")
SLATE_900  = colors.HexColor("#0F172A")
SLATE_700  = colors.HexColor("#334155")
SLATE_100  = colors.HexColor("#F1F5F9")
WHITE      = colors.white

ROLES = [
    ("Administrator", "Full control: users, departments, prefixes, audit, factory reset",
     "neulkarprathamesh@gmail.com", "Balaji@2026",
     [("Admin PIN", "1234"), ("Factory Reset PIN", "2580")],
     colors.HexColor("#DC2626"), colors.HexColor("#FEE2E2")),
    ("Manager", "Approves adjustments, extensions, refunds, cancellations",
     "manager@balajiconvent.in", "manager123",
     [], colors.HexColor("#7C3AED"), colors.HexColor("#EDE9FE")),
    ("Accountant", "Reviews collections, reconciles reports, defines fee structures",
     "accountant@balajiconvent.in", "account123",
     [], colors.HexColor("#0369A1"), colors.HexColor("#E0F2FE")),
    ("Cashier", "Collects fees, issues receipts, records reminder follow-ups",
     "cashier@balajiconvent.in", "cashier123",
     [], colors.HexColor("#059669"), colors.HexColor("#D1FAE5")),
]

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

c = canvas.Canvas(str(OUT), pagesize=A4)
c.setTitle("Balaji FeeHub - User Credentials")
c.setAuthor("Balaji Convent & Junior College")

# ---------- Header band ----------
c.setFillColor(SLATE_900)
c.rect(0, PAGE_H - 42 * mm, PAGE_W, 42 * mm, fill=1, stroke=0)
# amber accent stripe
c.setFillColor(AMBER)
c.rect(0, PAGE_H - 43 * mm, PAGE_W, 1.2 * mm, fill=1, stroke=0)

# Logo (circular clip via mask isn't trivial; draw the JPEG directly at header height)
if LOGO.exists():
    try:
        img = ImageReader(str(LOGO))
        c.saveState()
        # White ring background
        c.setFillColor(WHITE)
        c.circle(MARGIN + 14 * mm, PAGE_H - 21 * mm, 14 * mm, fill=1, stroke=0)
        c.drawImage(img, MARGIN, PAGE_H - 35 * mm, width=28 * mm, height=28 * mm, mask="auto",
                    preserveAspectRatio=True)
        c.restoreState()
    except Exception:
        pass

# Title
c.setFillColor(WHITE)
c.setFont("Helvetica-Bold", 22)
c.drawString(MARGIN + 34 * mm, PAGE_H - 18 * mm, "Balaji FeeHub")
c.setFont("Helvetica", 11)
c.setFillColor(AMBER)
c.drawString(MARGIN + 34 * mm, PAGE_H - 24 * mm, "User Credentials & Roles")
c.setFillColor(colors.HexColor("#94A3B8"))
c.setFont("Helvetica", 9)
c.drawString(MARGIN + 34 * mm, PAGE_H - 30 * mm,
             "Balaji Convent & Junior College  .  Butibori, Nagpur")

# Sub-header notice
y = PAGE_H - 54 * mm
c.setFillColor(SLATE_100)
c.roundRect(MARGIN, y - 14 * mm, PAGE_W - 2 * MARGIN, 12 * mm, 3, fill=1, stroke=0)
c.setFillColor(SLATE_700)
c.setFont("Helvetica-Bold", 10)
c.drawString(MARGIN + 4 * mm, y - 6 * mm, "CONFIDENTIAL - INTERNAL USE ONLY")
c.setFont("Helvetica", 9)
c.drawString(MARGIN + 4 * mm, y - 11 * mm,
             "Change every default password after first login. Rotate PINs each academic year.")
y -= 22 * mm

# ---------- Role cards ----------
for title, desc, email, password, extras, accent, tint in ROLES:
    CARD_H = 36 * mm + len(extras) * 5 * mm   # dynamic: extras (Admin PIN, Factory Reset PIN) get their own row
    if y - CARD_H < MARGIN:
        c.showPage()
        y = PAGE_H - MARGIN
    # Card background
    c.setFillColor(WHITE)
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, y - CARD_H, PAGE_W - 2 * MARGIN, CARD_H, 6, fill=1, stroke=1)
    # Accent stripe on the left
    c.setFillColor(accent)
    c.roundRect(MARGIN, y - CARD_H, 4 * mm, CARD_H, 2, fill=1, stroke=0)
    # Role badge
    c.setFillColor(tint)
    c.roundRect(MARGIN + 8 * mm, y - 10 * mm, 42 * mm, 7 * mm, 3, fill=1, stroke=0)
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(MARGIN + 29 * mm, y - 8 * mm, title.upper())
    # Description
    c.setFillColor(SLATE_700)
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN + 8 * mm, y - 16 * mm, desc)
    # Credentials grid via table
    data = [["Email", email], ["Password", password]]
    for label, value in extras:
        data.append([label, value])
    tbl = Table(data, colWidths=[28 * mm, PAGE_W - 2 * MARGIN - 44 * mm])
    tbl.setStyle(TableStyle([
        ("FONT",       (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT",       (1, 0), (1, -1), "Courier-Bold", 10),
        ("TEXTCOLOR",  (0, 0), (0, -1), SLATE_700),
        ("TEXTCOLOR",  (1, 0), (1, -1), SLATE_900),
        ("BACKGROUND", (1, 0), (1, -1), SLATE_100),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
    ]))
    tw, th = tbl.wrapOn(c, PAGE_W - 2 * MARGIN - 12 * mm, 60 * mm)
    tbl.drawOn(c, MARGIN + 8 * mm, y - 20 * mm - th)
    y -= CARD_H + 4 * mm

# ---------- Login hint footer ----------
if y - 30 * mm < MARGIN:
    c.showPage()
    y = PAGE_H - MARGIN
c.setFillColor(colors.HexColor("#FEF3C7"))
c.setStrokeColor(AMBER)
c.setLineWidth(0.6)
c.roundRect(MARGIN, y - 24 * mm, PAGE_W - 2 * MARGIN, 22 * mm, 4, fill=1, stroke=1)
c.setFillColor(AMBER_DARK)
c.setFont("Helvetica-Bold", 10)
c.drawString(MARGIN + 4 * mm, y - 6 * mm, "How to sign in")
c.setFillColor(SLATE_700)
c.setFont("Helvetica", 9)
c.drawString(MARGIN + 4 * mm, y - 11 * mm,
             "1. Double-click the Balaji FeeHub desktop icon (Windows-app mode - no browser).")
c.drawString(MARGIN + 4 * mm, y - 16 * mm,
             "2. Enter the email + password from the card that matches your role.")
c.drawString(MARGIN + 4 * mm, y - 21 * mm,
             "3. On first login, change your password from Profile > Change Password.")

# Footer
c.setFillColor(colors.HexColor("#94A3B8"))
c.setFont("Helvetica", 7.5)
c.drawString(MARGIN, 10 * mm,
             "Balaji Convent & Junior College  .  This document contains confidential access credentials.")
c.drawRightString(PAGE_W - MARGIN, 10 * mm, "Balaji FeeHub v1.0")

c.save()
size_kb = OUT.stat().st_size / 1024
print(f"OK  wrote {OUT}  ({size_kb:.1f} KB)")
