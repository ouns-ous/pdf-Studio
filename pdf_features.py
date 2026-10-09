"""Security and text stamping shared by previews and export."""

from html import escape
import pymupdf
from pdf_tools import selection


def watermark_settings(text, pages, count, size, opacity, position):
    if not text.strip() or len(text) > 200 or any(c in text for c in "\r\n\t"):
        raise ValueError("Enter one line of watermark text (1–200 characters).")
    try:
        size, opacity = int(size), int(opacity)
    except ValueError:
        raise ValueError("Font size and opacity must be whole numbers.") from None
    if not 8 <= size <= 100 or not 5 <= opacity <= 100:
        raise ValueError("Use font size 8–100 and opacity 5–100%.")
    if position not in ("Top", "Center", "Bottom"):
        raise ValueError("Choose Top, Center or Bottom.")
    try:
        indices = selection(pages, count)
    except ValueError:
        raise ValueError(f"Use watermark pages 1–{count}, for example 1,3–5 (use a hyphen).") from None
    return dict(text=text, indices=indices, size=size, opacity=opacity, position=position)


def stamp_page(page, settings):
    # Map the displayed placement into the existing page coordinates.
    # Keep rotation and crop boxes intact, including previously cropped PDFs.
    width, height = page.rect.width, page.rect.height
    margin = min(20, width / 10, height / 10)
    band = min(settings["size"] * 2.5, height - margin * 2)
    top = {"Top": margin, "Center": (height - band) / 2,
           "Bottom": height - margin - band}[settings["position"]]
    box = pymupdf.Rect(margin, top, width - margin, top + band)
    # HTML layout supports Unicode shaping and font fallback. Escape user text.
    page.insert_htmlbox(
        box * page.derotation_matrix,
        '<div dir="auto">' + escape(settings["text"]) + '</div>',
        css=f"* {{font-family: sans-serif; font-size: {settings['size']}pt; color: #666666; text-align: center; margin: 0;}}",
        opacity=settings["opacity"] / 100,
        overlay=True,
        rotate=page.rotation,
    )


def validate_password(password, confirmation):
    if not 8 <= len(password) <= 40 or len(password.encode("utf-8")) > 40:
        raise ValueError("Use a password of 8–40 characters (at most 40 UTF-8 bytes).")
    if password != confirmation:
        raise ValueError("The passwords do not match.")


def authenticate(doc, password):
    if doc.needs_pass and not doc.authenticate(password):
        raise ValueError("Incorrect PDF password. Choose the file again to retry.")



def chosen_pages(text, count):
    try:
        return sorted(selection(text, count))
    except ValueError:
        raise ValueError(f"Use pages 1–{count}, for example 1,3-5; leave blank for all.") from None


def page_number_settings(pages, count, start, size, position, style):
    try:
        start, size = int(start), int(size)
    except ValueError:
        raise ValueError("Starting number and font size must be whole numbers.") from None
    if not 1 <= start <= 999999 or not 8 <= size <= 40:
        raise ValueError("Use starting number 1–999999 and font size 8–40 pt.")
    if position not in ("Top", "Bottom") or style not in ("Number", "Page n of total"):
        raise ValueError("Choose a numbering format and position.")
    return dict(indices=chosen_pages(pages, count), start=start, size=size,
                position=position, style=style)


def crop_settings(pages, count, margins):
    try:
        values = [int(value) for value in margins]
    except ValueError:
        raise ValueError("Crop margins must be whole percentages.") from None
    left, top, right, bottom = values
    if any(value < 0 or value > 90 for value in values) or left + right >= 95 or top + bottom >= 95:
        raise ValueError("Use margins 0–90%; opposite margins must total less than 95%.")
    if not any(values):
        raise ValueError("Set at least one crop margin greater than zero.")
    return dict(indices=chosen_pages(pages, count), margins=values)


def apply_page_edit(page, mode, settings):
    if page.number not in settings["indices"]:
        return
    if mode == "Watermark":
        stamp_page(page, settings)
    elif mode == "Page numbers":
        number = settings["start"] + settings["indices"].index(page.number)
        total = settings["start"] + len(settings["indices"]) - 1
        text = str(number) if settings["style"] == "Number" else f"Page {number} of {total}"
        stamp_page(page, dict(text=text, size=settings["size"], opacity=100,
                             position=settings["position"]))
    elif mode == "Crop PDF":
        rect = page.rect
        left, top, right, bottom = settings["margins"]
        displayed = pymupdf.Rect(rect.width * left / 100, rect.height * top / 100,
                                 rect.width * (1 - right / 100), rect.height * (1 - bottom / 100))
        unrotated = displayed * page.derotation_matrix
        offset = page.cropbox.tl
        page.set_cropbox(pymupdf.Rect(unrotated.tl + offset, unrotated.br + offset))
