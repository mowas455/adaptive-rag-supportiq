"""Write two layout-rich NexCart PDFs used as the knowledge base.

Markdown in data/docs/ is source copy only. Ingest reads data/pdfs/*.pdf.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import PDF_DIR  # noqa: E402

NAVY = HexColor("#1b365d")
TEAL = HexColor("#0e7c7b")
RULE = HexColor("#d6dde6")
MUTED = HexColor("#5b6570")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=TEAL,
            tracking=1.2,
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=NAVY,
            leading=22,
            spaceAfter=8,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=HexColor("#1f2933"),
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            textColor=MUTED,
            spaceAfter=12,
        ),
        "li": ParagraphStyle(
            "li",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=HexColor("#1f2933"),
        ),
    }


def _header_footer(title: str, doc_id: str):
    def _draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, letter[1] - 36, letter[0], 36, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(54, letter[1] - 22, "NexCart SupportIQ  ·  Internal knowledge")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(letter[0] - 54, letter[1] - 22, doc_id)
        canvas.setFillColor(TEAL)
        canvas.rect(0, 0, letter[0], 28, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(54, 12, title)
        canvas.drawRightString(letter[0] - 54, 12, f"Page {doc.page}")
        canvas.restoreState()

    return _draw


def _bullets(items: list[str], styles: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, styles["li"]), leftIndent=8) for item in items],
        bulletType="1",
        start="1",
        leftIndent=18,
        spaceAfter=10,
    )


def write_return_policy(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=48,
        title="NexCart Return & Exchange Policy",
        author="NexCart Policy Team",
    )
    s = []
    s.append(Paragraph("POLICY  ·  RET-2026-03", styles["kicker"]))
    s.append(Paragraph("NexCart Return &amp; Exchange Policy", styles["h1"]))
    s.append(
        Paragraph(
            "Last updated: March 1, 2026. Applies to orders placed through NexCart.com and "
            "the NexCart Seller Portal in the United States and Canada. International "
            "marketplace orders follow the seller's listed policy unless NexCart is the "
            "merchant of record.",
            styles["meta"],
        )
    )
    s.append(Paragraph("Return window", styles["h2"]))
    s.append(
        Paragraph(
            "Most unused items may be returned within <b>30 days of delivery</b> for a full "
            "refund to the original payment method. The return window is measured from the "
            "date the carrier marks the package as delivered, not from the order date. "
            "Seasonal and promotional items marked Final Sale are not eligible for return.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "Electronics in the NexCart Basics line (chargers, earbuds, smart plugs) have a "
            "<b>15-day</b> return window because of restocking and firmware pairing. Opened "
            "software, gift cards, and perishable grocery add-ons cannot be returned.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "If a delivery is delayed more than 7 calendar days past the quoted window, we "
            "extend the return window by the number of delay days. Contact support with the "
            "order number; the extension is applied automatically once shipping scans confirm "
            "the delay.",
            styles["body"],
        )
    )
    table = Table(
        [
            [Paragraph("<b>Category</b>", styles["li"]), Paragraph("<b>Window</b>", styles["li"])],
            [Paragraph("Most unused items", styles["li"]), Paragraph("30 days from delivery", styles["li"])],
            [Paragraph("NexCart Basics electronics", styles["li"]), Paragraph("15 days from delivery", styles["li"])],
            [Paragraph("Software, gift cards, perishables", styles["li"]), Paragraph("Not eligible", styles["li"])],
        ],
        colWidths=[3.4 * inch, 3.0 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#e8eef5")),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    s.append(table)
    s.append(Spacer(1, 8))
    s.append(Paragraph("Condition requirements", styles["h2"]))
    s.append(
        Paragraph(
            "Items must be unused, in original packaging, with all accessories, manuals, and "
            "hang-tags. We inspect returns at the Dayton, Ohio reverse-logistics hub. Light "
            "wear from trying on apparel is acceptable. Stains, odors, missing parts, or "
            "evidence of installation (for example, a smart lock that was drilled into a door) "
            "will be classified as damaged and may be refunded at a reduced amount or rejected.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "Photographs of the item and packaging help us process a return before the package "
            "arrives. You can upload photos in the Returns Center. This does not replace inspection.",
            styles["body"],
        )
    )
    s.append(Paragraph("How to start a return", styles["h2"]))
    s.append(
        _bullets(
            [
                "Sign in to your NexCart account and open <b>Orders → Request return</b>.",
                "Select items and a reason (wrong size, damaged, changed mind, not as described).",
                "Print the prepaid label or use the QR code at a UPS Access Point. Label cost is "
                "deducted from the refund for change-of-mind returns ($6.99 domestic). Labels are "
                "free for damaged, defective, or incorrect items.",
                "Drop off the package within 14 days of generating the label. Labels unused after "
                "14 days expire and must be regenerated.",
            ],
            styles,
        )
    )
    s.append(
        Paragraph(
            "You will receive an email when the warehouse scans the return. Refunds typically "
            "post <b>3–5 business days after inspection</b>. Store credit posts the same day as "
            "inspection and includes a 5% bonus on change-of-mind returns.",
            styles["body"],
        )
    )
    s.append(PageBreak())
    s.append(Paragraph("Exchanges, warranty, and exceptions", styles["h2"]))
    s.append(
        Paragraph(
            "Size and color exchanges for apparel and home textiles are treated as a new order "
            "at the current price plus a $4.99 handling fee, waived for NexCart Plus members. "
            "Defective items can be exchanged like-for-like at no charge, including expedited "
            "replacement shipping.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "Manufacturer defects discovered after the return window may still be covered under "
            "the 12-month NexCart Basics limited warranty. Warranty claims are not returns: we "
            "repair, replace, or issue a prorated credit. Do not use the Returns Center for "
            "warranty claims; open a ticket under <b>Account → Warranty</b>.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "Custom-engraved goods, made-to-order furniture, and items fulfilled by third-party "
            "sellers labeled Ships from partner follow the partner's policy displayed on the "
            "product page. NexCart will help you contact the seller but cannot override their window.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "If you received a damaged shipment, photograph the box and contents within 48 hours "
            "of delivery. We will arrange a replacement before you ship the damaged unit back "
            "when inventory is available. An electric scooter or other vehicle accessory returned "
            "45 days after delivery is outside the 30-day unused-item window and is not eligible "
            "unless a delay extension or warranty claim applies.",
            styles["body"],
        )
    )
    doc.build(
        s,
        onFirstPage=_header_footer("Return & Exchange Policy", "RET-2026-03"),
        onLaterPages=_header_footer("Return & Exchange Policy", "RET-2026-03"),
    )


def write_troubleshooting(path: Path) -> None:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=48,
        title="NexCart Product Troubleshooting Guide",
        author="NexCart Hardware Support",
    )
    s = []
    s.append(Paragraph("HARDWARE  ·  HW-TS-2026-01", styles["kicker"]))
    s.append(Paragraph("NexCart Product Troubleshooting Guide", styles["h1"]))
    s.append(
        Paragraph(
            "This guide covers the NexCart Basics hardware line: PulseBuds wireless earbuds, "
            "HomePlug mini smart plugs, LockStep smart deadbolt, and GlowBar LED light strip. "
            "Keep the device nearby. Most issues are firmware, power, or pairing related.",
            styles["meta"],
        )
    )
    s.append(Paragraph("PulseBuds will not pair", styles["h2"]))
    s.append(
        _bullets(
            [
                "Place both earbuds in the case, close the lid for 10 seconds, then open it. "
                "The case LED should pulse white.",
                'On your phone, forget the previous "NexCart PulseBuds" Bluetooth entry.',
                "Press and hold the case button for 8 seconds until the LED flashes blue. "
                "That is pairing mode.",
                "Connect from Bluetooth settings. Do not use Fast Pair prompts from a previous session.",
            ],
            styles,
        )
    )
    s.append(
        Paragraph(
            "If only one earbud plays audio, reset the pair: both buds in the case, hold the "
            "case button 15 seconds until the LED turns amber, then pair again. Firmware 2.4.1 "
            "(January 2026) fixed a left-bud mute bug after iOS 18.4; update through the NexCart "
            "app under <b>Devices → PulseBuds → Firmware</b>.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "Battery drain overnight usually means the case lid magnet is not seating. Clean the "
            "charging pins with a dry cotton swab. Do not use alcohol on the mesh.",
            styles["body"],
        )
    )
    s.append(Paragraph("HomePlug mini does not appear in the app", styles["h2"]))
    s.append(
        Paragraph(
            "HomePlug requires 2.4 GHz Wi-Fi. 5 GHz-only networks will fail silently. Create a "
            "2.4 GHz SSID or enable band steering compatibility. The plug LED should blink amber "
            "during setup and turn solid green when joined.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "If the LED is red, the plug cannot reach your router. Move it closer for first "
            "pairing, then use the app's Relocate flow. Factory reset: hold the side button 12 "
            "seconds until the LED blinks red-green. Do not connect HomePlug to space heaters, "
            "window AC units, or devices over 10A. The thermal cutoff will trip and the LED will "
            "blink red twice. Unplug for 5 minutes to reset. Repeated trips void the warranty.",
            styles["body"],
        )
    )
    s.append(PageBreak())
    s.append(Paragraph("LockStep deadbolt will not auto-unlock", styles["h2"]))
    s.append(
        Paragraph(
            "Auto-unlock needs Bluetooth plus location permission set to <b>Always</b> on "
            "iOS/Android. Geofence radius is 30 meters. If you live in a dense apartment, reduce "
            "the radius to 15 meters in <b>Devices → LockStep → Geofence</b> to avoid unlocking "
            "in the hallway.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "After a deadbolt replacement or door strike adjustment, recalibrate: open the app, "
            "Calibrate motor, and run the door through lock/unlock twice. A grinding sound means "
            "the strike plate is misaligned; stop and use the mechanical key. Continuing can burn "
            "the motor.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "LockStep stores 50 PIN codes and 10 scheduled guest codes. Guest codes expire at the "
            "time you set; they cannot be extended—create a new code. If the keypad is unresponsive "
            "in cold weather (below 20°F / −6°C), warm the unit for a minute; this is a known "
            "limitation, not a defect. Battery pack: four AA lithium batteries last about 8 months. "
            "Alkaline batteries last 4–5 months and may fail in winter. Low-battery chirps start at "
            "20%. Replace both pairs together. Do not mix chemistries.",
            styles["body"],
        )
    )
    s.append(Paragraph("GlowBar LED strip flickers or shows the wrong color", styles["h2"]))
    s.append(
        Paragraph(
            "Flicker on dim scenes is usually an overloaded USB-C power adapter. Use the included "
            "24W adapter, not a phone charger. Addressable color errors (one segment stuck green) "
            "often mean a kinked data line. Unplug, straighten the strip, and power-cycle.",
            styles["body"],
        )
    )
    s.append(
        Paragraph(
            "The strip supports Matter over Wi-Fi on firmware 1.8+. If Matter pairing fails, "
            "remove the accessory from Apple Home / Google Home first, then retry from the "
            "NexCart app <b>Works with</b>.",
            styles["body"],
        )
    )
    s.append(Paragraph("Still stuck?", styles["h2"]))
    s.append(
        Paragraph(
            "Collect the device serial (inside the battery door or on the QR card), app version, "
            "and phone OS. Open <b>Help → Hardware ticket</b>. Hardware replacements for "
            "manufacturing defects are processed under the 12-month Basics warranty, not the "
            "15-day electronics return window.",
            styles["body"],
        )
    )
    doc.build(
        s,
        onFirstPage=_header_footer("Product Troubleshooting Guide", "HW-TS-2026-01"),
        onLaterPages=_header_footer("Product Troubleshooting Guide", "HW-TS-2026-01"),
    )


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    policy = PDF_DIR / "nexcart_return_exchange_policy.pdf"
    guide = PDF_DIR / "nexcart_product_troubleshooting.pdf"
    write_return_policy(policy)
    write_troubleshooting(guide)
    print(f"Wrote {policy}")
    print(f"Wrote {guide}")


if __name__ == "__main__":
    main()
