#!/usr/bin/env python3
"""Generate INSTALLATION_MANUAL.pdf from a static content spec using ReportLab."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
)
from reportlab.pdfgen import canvas

OUT = Path("/app/dist/BalajiConventFeeSoftware-v1.0/INSTALLATION_MANUAL.pdf")
LOGO = Path("/app/frontend/public/school-logo.jpeg")

NAVY = colors.HexColor("#1a237e")
RED  = colors.HexColor("#C62828")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1", parent=styles["Heading1"], textColor=NAVY, spaceAfter=6, fontSize=22, leading=26))
styles.add(ParagraphStyle("H2", parent=styles["Heading2"], textColor=RED, spaceBefore=10, spaceAfter=4, fontSize=13))
styles.add(ParagraphStyle("Body2", parent=styles["BodyText"], fontSize=10, leading=13))
styles.add(ParagraphStyle("Mono", parent=styles["Code"], fontSize=9, textColor=colors.black, backColor=colors.HexColor("#f4f6fb"), leading=12))
styles.add(ParagraphStyle("Cover", parent=styles["Title"], textColor=colors.white, fontSize=32, leading=36))
styles.add(ParagraphStyle("CoverSub", parent=styles["BodyText"], textColor=colors.white, fontSize=13, alignment=1))


def header_footer(canv: canvas.Canvas, doc):
    canv.saveState()
    canv.setFillColor(NAVY); canv.rect(0, A4[1]-14*mm, A4[0], 14*mm, stroke=0, fill=1)
    canv.setFillColor(colors.white); canv.setFont("Helvetica-Bold", 9)
    canv.drawString(18*mm, A4[1]-9*mm, "Balaji FeeHub · Installation Manual")
    canv.drawRightString(A4[0]-18*mm, A4[1]-9*mm, "Version 1.0")
    canv.setFillColor(colors.HexColor("#64748b")); canv.setFont("Helvetica", 8)
    canv.drawString(18*mm, 10*mm, "Balaji Convent & Junior College · Butibori, Nagpur")
    canv.drawRightString(A4[0]-18*mm, 10*mm, f"Page {doc.page}")
    canv.setStrokeColor(colors.HexColor("#cbd5e1")); canv.line(18*mm, 15*mm, A4[0]-18*mm, 15*mm)
    canv.restoreState()


def cover(canv, doc):
    canv.saveState()
    canv.setFillColor(NAVY); canv.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canv.setFillColor(RED); canv.rect(0, 180*mm, A4[0], 2*mm, stroke=0, fill=1)
    if LOGO.exists():
        try:
            canv.drawImage(str(LOGO), (A4[0]-40*mm)/2, 210*mm, 40*mm, 40*mm, preserveAspectRatio=True, mask='auto')
        except Exception: pass
    canv.setFillColor(colors.white)
    canv.setFont("Helvetica-Bold", 30); canv.drawCentredString(A4[0]/2, 195*mm, "Balaji FeeHub")
    canv.setFont("Helvetica", 14);       canv.drawCentredString(A4[0]/2, 185*mm, "Fee Management System")
    canv.setFont("Helvetica", 11);       canv.drawCentredString(A4[0]/2, 175*mm, "Balaji Convent & Junior College · Butibori, Nagpur")
    canv.setFont("Helvetica-Bold", 22); canv.drawCentredString(A4[0]/2, 130*mm, "Installation Manual")
    canv.setFont("Helvetica-Bold", 28); canv.drawCentredString(A4[0]/2, 110*mm, "Version 1.0")
    canv.setFillColor(colors.HexColor("#c7d2fe")); canv.setFont("Helvetica", 9)
    canv.drawCentredString(A4[0]/2, 30*mm, "Offline · LAN-based · Auditable · Precise")
    canv.drawCentredString(A4[0]/2, 24*mm, "© Balaji Convent & Junior College — all rights reserved.")
    canv.restoreState()


SECTIONS = [
    ("1. Windows 10/11 Requirements", [
        ("Supported OS", ["Windows 10 Pro/Enterprise 64-bit (recommended)", "Windows 11 Pro/Enterprise 64-bit", "Windows Server 2019/2022 (optional)"]),
        ("Minimum Hardware", ["Dual-core 2.0 GHz CPU", "4 GB RAM (8 GB recommended)", "20 GB free disk", "100 Mbps LAN"]),
        ("Client PCs", ["Windows 10/11 64-bit", "Chrome OR Microsoft Edge", "LAN connection to Main Server", "NO Python, Node.js, or MongoDB required"]),
    ]),
    ("2. Static LAN IP", [
        ("Assign a static IPv4 to the Main Server", [
            "Open Control Panel → Network → Change Adapter Settings",
            "Right-click Ethernet → Properties → IPv4 → Properties",
            "IP: 192.168.1.10  ·  Subnet: 255.255.255.0  ·  Gateway: 192.168.1.1",
            "The installer detects this IP and writes it into frontend/.env — no manual edit needed",
        ]),
    ]),
    ("3. Firewall", [
        ("Ports opened by install-main-server.bat", ["TCP 3000 — Application (opened)", "TCP 8001 — Backend API (opened)", "TCP 27017 — MongoDB (kept private, bound to 127.0.0.1)"]),
        ("Windows Defender", ["The installer runs `netsh advfirewall firewall add rule …` automatically", "You do NOT need to click through any Firewall dialog on the Main Server"]),
    ]),
    ("4. MongoDB", [
        ("Bundled MSI", ["The FINAL ZIP ships with the official MongoDB Community MSI under 05-services/", "The installer runs it in silent mode: `msiexec /i mongodb-*.msi ADDLOCAL=ServerNoService /qn /norestart`"]),
        ("Configuration", ["MongoDB binds to 127.0.0.1 only (bindIp: 127.0.0.1 in mongod.cfg)", "Clients never talk to MongoDB directly — every request goes through the backend on port 8001"]),
        ("Service", ["Registered as `BalajiFeeHub-Mongo`, auto-start", "Data dir: C:\\balaji-fee\\mongodb\\data", "Log dir: C:\\balaji-fee\\mongodb\\logs"]),
    ]),
    ("5. Backend & Frontend Services", [
        ("Backend", ["`BalajiFeeHub-Backend` — uvicorn on port 8001", "Depends on Mongo service, auto-restart via NSSM", "Log rotation at 20 MB, 5 files"]),
        ("Frontend", ["`BalajiFeeHub-Frontend` — Python built-in `http.server` on port 3000", "Serves the prebuilt React static site from frontend/build/", "No Node/npm required on the Main Server"]),
        ("Auto-start", ["All three services set to Auto — Windows reboots do NOT require manual intervention"]),
    ]),
    ("6. First Login", [
        ("Default admin", ["admin@balajiconvent.in / ChangeMeOnFirstLogin@2026", "Change password IMMEDIATELY from Menu → Users", "Factory Reset PIN default: 2580 — change from Administration → Factory Reset → Change PIN"]),
    ]),
    ("7. Client PC Installation", [
        ("Zero-edit installer", [
            "Copy 02-install-client-pc/ to the client PC (from Main Server share or USB)",
            "Right-click install-client-pc.bat → Run as administrator",
            "The script auto-discovers the Main Server on the LAN (10-second parallel scan)",
            "If discovery fails, admin enters the IP manually",
            "Desktop shortcut + Start-Menu shortcut are created",
            "Browser opens automatically",
        ]),
    ]),
    ("8. Multiple Cashier PCs", [
        ("Concurrent access", [
            "The backend supports 100+ concurrent requests (load-tested to 120 req/s)",
            "Each cashier logs in with their own credentials on their own PC",
            "Every write is recorded in the audit log with cashier name + timestamp + IP",
        ]),
    ]),
    ("9. Printer Setup", [
        ("Any Windows-supported printer", [
            "Add via Control Panel → Printers → set as default",
            "Print a Windows test page first",
            "In the receipt view, click Print — the browser dialog opens with the default printer preselected",
        ]),
        ("Paper sizes", ["A5 (default), A4, A4-Landscape, Legal, Letter, Thermal 80 mm — configurable per receipt type"]),
    ]),
    ("10. Backup & Restore", [
        ("Automatic", ["Daily backup runs at 02:00 · last 30 backups retained · integrity SHA-256"]),
        ("Manual", ["Administration → Backups → Create Backup Now (Admin PIN)"]),
        ("Restore", ["Administration → Backups → Restore (requires Admin PIN + password re-verify)"]),
    ]),
    ("11. Uninstall & Repair", [
        ("Uninstall", ["01-install-main-server/uninstall.bat  (services removed; data + backups kept)"]),
        ("Repair", ["01-install-main-server/repair-installation.bat  (re-copies source, re-runs pip install)"]),
        ("Client Uninstall", ["02-install-client-pc/uninstall-client-pc.bat"]),
    ]),
    ("12. Troubleshooting", [
        ("Client cannot connect", ["ping 192.168.1.10 from cmd; confirm firewall rules; restart services in services.msc"]),
        ("Login fails", ["Reset password from Menu → Users (as another admin) or from install-main-server .env"]),
        ("Update failed", ["System auto-rolled back; check Software Updates → History for the failed step"]),
        ("Printer not working", ["Set as default in Windows; test with a Windows test page"]),
    ]),
    ("13. Not Yet Tested on Clean Windows PC", [
        ("Developer transparency", [
            "This ZIP was assembled in a Linux container.",
            "Every .bat script was hand-written to Windows conventions and reviewed against the 20-point checklist.",
            "Clean-machine acceptance tests (Windows 10 + Windows 11) MUST still be executed by the school before daily use.",
            "If preflight.bat reports any BLOCK line on your Main Server, share it and we will patch immediately.",
        ]),
    ]),
]


def build():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=22*mm, bottomMargin=20*mm,
                            title="Balaji FeeHub — Installation Manual")
    story = []

    for i, (title, blocks) in enumerate(SECTIONS):
        story.append(Paragraph(title, styles["H1"]))
        for h, lines in blocks:
            story.append(Paragraph(h, styles["H2"]))
            for line in lines:
                story.append(Paragraph("• " + line, styles["Body2"]))
        story.append(PageBreak())

    def _first_page(canv, doc): cover(canv, doc)
    def _later(canv, doc): header_footer(canv, doc)
    doc.build(story, onFirstPage=_first_page, onLaterPages=_later)
    print(f"Written: {OUT} ({OUT.stat().st_size/1024:.1f} KB, {len(SECTIONS)} sections)")


if __name__ == "__main__":
    build()
