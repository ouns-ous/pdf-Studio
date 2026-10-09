"""Security and text stamping shared by previews and export."""

from html import escape
from collections import OrderedDict
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


class StampRenderer:
    """Reuse stamp PDFs within a job instead of embedding the same fonts per page."""

    def __init__(self):
        self.templates = OrderedDict()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for source, _ in self.templates.values():
            source.close()
        self.templates.clear()

    def apply(self, page, settings):
        width, height = page.rect.width, page.rect.height
        margin = min(20, width / 10, height / 10)
        key = (width, height, settings["text"], settings["size"], settings["opacity"])
        if key not in self.templates:
            source = pymupdf.open()
            try:
                stamp = source.new_page(width=width, height=height)
                band = min(settings["size"] * 2.5, height - margin * 2)
                stamp.insert_htmlbox(
                    pymupdf.Rect(margin, margin, width - margin, margin + band),
                    '<div dir="auto">' + escape(settings["text"]) + '</div>',
                    css=f"* {{font-family: sans-serif; font-size: {settings['size']}pt; color: #666666; text-align: center; margin: 0;}}",
                    opacity=settings["opacity"] / 100,
                )
                bounds = pymupdf.Rect()
                for block in stamp.get_text("blocks"):
                    if block[4].strip():
                        bounds |= pymupdf.Rect(block[:4])
                if bounds.is_empty:
                    raise ValueError("The watermark must contain visible text.")
                self.templates[key] = (source, bounds)
            except Exception:
                source.close()
                raise
        self.templates.move_to_end(key)
        source, bounds = self.templates[key]
        top = {"Top": margin, "Center": (height - bounds.height) / 2,
               "Bottom": height - margin - bounds.height}[settings["position"]]
        left = (width - bounds.width) / 2
        target = pymupdf.Rect(left, top, left + bounds.width, top + bounds.height)
        target = target * page.derotation_matrix
        rotation = page.rotation
        # show_pdf_page needs the unrotated crop translation as well as the
        # displayed orientation. Restore rotation even if insertion fails.
        page.set_rotation(0)
        try:
            page.show_pdf_page(target, source, 0, clip=bounds,
                               rotate=rotation, overlay=True)
        finally:
            page.set_rotation(rotation)
        if len(self.templates) > 32:
            old_source, _ = self.templates.popitem(last=False)[1]
            old_source.close()


def stamp_page(page, settings, renderer=None):
    if renderer is None:
        with StampRenderer() as renderer:
            renderer.apply(page, settings)
    else:
        renderer.apply(page, settings)


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


def apply_page_edit(page, mode, settings, renderer=None, positions=None):
    if positions is None:
        positions = {number: rank for rank, number in enumerate(settings["indices"])}
    if page.number not in positions:
        return
    if mode == "Watermark":
        stamp_page(page, settings, renderer)
    elif mode == "Page numbers":
        number = settings["start"] + positions[page.number]
        total = settings["start"] + len(settings["indices"]) - 1
        text = str(number) if settings["style"] == "Number" else f"Page {number} of {total}"
        stamp_page(page, dict(text=text, size=settings["size"], opacity=100,
                             position=settings["position"]), renderer)
    elif mode == "Crop PDF":
        rect = page.rect
        left, top, right, bottom = settings["margins"]
        displayed = pymupdf.Rect(rect.width * left / 100, rect.height * top / 100,
                                 rect.width * (1 - right / 100), rect.height * (1 - bottom / 100))
        unrotated = displayed * page.derotation_matrix
        offset = page.cropbox.tl
        page.set_cropbox(pymupdf.Rect(unrotated.tl + offset, unrotated.br + offset))
