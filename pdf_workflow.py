"""Plain task state and output contracts, independent of the UI."""

from dataclasses import dataclass, field
from copy import deepcopy
from pdf_tools import selection
from pdf_features import (validate_password, watermark_settings, chosen_pages,
                          page_number_settings, crop_settings)

TOOLS = {
    "Merge PDF": (
        "Organize PDF",
        "Combine PDFs in the order you choose.",
        "#f5684b",
        "↘↖",
    ),
    "Split PDF": (
        "Organize PDF",
        "Split by ranges or extract exactly the pages you need.",
        "#f5684b",
        "↖↘",
    ),
    "Compress PDF": (
        "Optimize PDF",
        "Reduce file size with a choice of image quality.",
        "#8cba59",
        "⇲",
    ),
    "Organize PDF": (
        "Organize PDF",
        "Reorder, rotate and remove pages. Undo any change.",
        "#f5684b",
        "A B",
    ),
    "Remove pages": (
        "Organize PDF",
        "Mark the pages to remove and preview what stays.",
        "#f5684b",
        "×",
    ),
    "Rotate PDF": (
        "Edit PDF",
        "Preview and apply rotation to individual pages or all pages.",
        "#ab6796",
        "↻",
    ),
    "Images to PDF": (
        "Convert PDF",
        "Arrange images and choose page size, orientation and margins.",
        "#d4c52c",
        "▧",
    ),
}
BATCH = {"Merge PDF", "Compress PDF", "Images to PDF"}
TOOLS.update({
    "Protect PDF": ("PDF Security", "Require a password to open your PDF.", "#497dae", "◆"),
    "Unlock PDF": ("PDF Security", "Remove PDF encryption using its password.", "#497dae", "◇"),
    "Watermark": ("Edit PDF", "Preview a text watermark on the pages you choose.", "#ab6796", "T"),
    "PDF to JPG": ("Convert PDF", "Export PDF pages as JPG images at your chosen resolution.", "#d4c52c", "JPG"),
    "Page numbers": ("Edit PDF", "Add page numbers with your choice of range and starting number.", "#ab6796", "1 2"),
    "Crop PDF": ("Edit PDF", "Trim visible page margins and preview the result.", "#ab6796", "⊡"),
})
PAGE_EDITS = {"Watermark", "Page numbers", "Crop PDF"}


@dataclass
class Session:
    mode: str
    files: list = field(default_factory=list)
    counts: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    order: list = field(default_factory=list)
    removed: set = field(default_factory=set)
    rotations: dict = field(default_factory=dict)
    selected: set = field(default_factory=set)
    ranges: list = field(default_factory=lambda: [("1", "1")])
    split_mode: str = "Custom"
    fixed: str = "1"
    combine: bool = False
    page_text: str = ""
    compression: str = "Recommended compression"
    page_size: str = "A4"
    orientation: str = "Portrait"
    margin: str = "20"
    offset: int = 0
    loaded: bool = False
    result: dict | None = None
    history: list = field(default_factory=list)
    password: str = field(default="", repr=False)
    confirmation: str = field(default="", repr=False)
    input_password: str = field(default="", repr=False)
    watermark_text: str = "CONFIDENTIAL"
    watermark_pages: str = ""
    watermark_size: str = "36"
    watermark_opacity: str = "30"
    watermark_position: str = "Center"
    target_pages: str = ""
    jpg_dpi: str = "150"
    jpg_quality: str = "85"
    number_start: str = "1"
    number_size: str = "12"
    number_position: str = "Bottom"
    number_style: str = "Number"
    crop_left: str = "5"
    crop_top: str = "5"
    crop_right: str = "5"
    crop_bottom: str = "5"

    def watermark(self):
        return watermark_settings(self.watermark_text, self.watermark_pages,
                                  self.page_count, self.watermark_size,
                                  self.watermark_opacity, self.watermark_position)

    def page_edit(self):
        if self.mode == "Watermark":
            return self.watermark()
        if self.mode == "Page numbers":
            return page_number_settings(self.target_pages, self.page_count, self.number_start,
                                        self.number_size, self.number_position, self.number_style)
        if self.mode == "Crop PDF":
            return crop_settings(self.target_pages, self.page_count,
                                 [self.crop_left, self.crop_top, self.crop_right, self.crop_bottom])
        return None

    @property
    def page_count(self):
        return self.counts[0] if self.counts else 0

    def checkpoint(self):
        fields = ("files", "order", "removed", "rotations", "selected")
        self.history.append({key: deepcopy(getattr(self, key)) for key in fields})
        self.history = self.history[-30:]

    def undo(self):
        if self.history:
            for key, value in self.history.pop().items():
                setattr(self, key, value)
            self.offset = 0
            return True
        return False

    def groups(self):
        count = self.page_count
        if self.split_mode == "Custom":
            if not self.ranges:
                raise ValueError("Add at least one range.")
            groups = []
            for index, (a, b) in enumerate(self.ranges, 1):
                try:
                    start, end = int(a), int(b)
                except ValueError:
                    raise ValueError(
                        f"Range {index}: enter a start and an end page."
                    ) from None
                if not 1 <= start <= end <= count:
                    raise ValueError(
                        f"Range {index}: use pages 1–{count}, with start ≤ end."
                    )
                groups.append(list(range(start - 1, end)))
            return groups
        if self.split_mode == "Fixed":
            try:
                size = int(self.fixed)
            except ValueError:
                raise ValueError("Enter a whole number of pages per file.") from None
            if not 1 <= size <= count:
                raise ValueError(f"Pages per file must be between 1 and {count}.")
            return [list(range(i, min(i + size, count))) for i in range(0, count, size)]
        if not self.page_text.strip():
            raise ValueError("Choose pages to extract, or select all pages.")
        return [[i] for i in selection(self.page_text, count)]

    def contract(self):
        if not self.files:
            raise ValueError("Select files to get started.")
        if not self.loaded:
            raise ValueError("Checking files and loading previews…")
        if self.errors:
            raise ValueError("Remove or replace the files marked with an error.")
        if self.mode == "Merge PDF" and len(self.files) < 2:
            raise ValueError("Add at least one more PDF to merge your files.")
        count, pages, warning = 1, sum(self.counts), ""
        if self.mode == "Protect PDF":
            validate_password(self.password, self.confirmation)
            warning = "The saved PDF will require your password to open."
        elif self.mode == "Unlock PDF":
            warning = "The saved copy will open without a password."
        elif self.mode == "Watermark":
            settings = self.watermark()
            warning = f"Text watermark on {len(settings['indices'])} page(s). Long text shrinks to fit."
        elif self.mode in PAGE_EDITS:
            settings = self.page_edit()
            warning = f"Apply changes to {len(settings['indices'])} page(s)."
        elif self.mode == "PDF to JPG":
            count = pages = len(chosen_pages(self.target_pages, self.page_count))
            if self.jpg_dpi not in ("72", "150", "300") or self.jpg_quality not in ("60", "85", "95"):
                raise ValueError("Choose the image resolution and quality.")
            warning = f"{self.jpg_dpi} DPI · JPG quality {self.jpg_quality}%."
        if self.mode == "Split PDF":
            groups = self.groups()
            pages = sum(map(len, groups))
            count = 1 if self.combine else len(groups)
            flat = [i for group in groups for i in group]
            if self.combine and len(set(flat)) != len(flat):
                warning = (
                    "Overlapping pages will appear more than once, in range order."
                )
        elif self.mode in ("Remove pages", "Organize PDF"):
            pages = self.page_count - len(self.removed)
            if pages == 0:
                raise ValueError(
                    "Keep at least one page. Restore a marked page to continue."
                )
            if self.mode == "Remove pages" and not self.removed:
                raise ValueError("Click the pages you want to remove.")
        elif self.mode == "Rotate PDF" and not any(self.rotations.values()):
            raise ValueError("Rotate a page, or apply a rotation to all pages.")
        elif self.mode == "Compress PDF":
            count = len(self.files)
        elif self.mode == "Images to PDF":
            try:
                margin = int(self.margin)
                if not 0 <= margin <= 100:
                    raise ValueError()
            except ValueError:
                raise ValueError("Margins must be between 0 and 100 points.") from None
        return {
            "count": count,
            "pages": pages,
            "extension": ".zip" if count > 1 else (".jpg" if self.mode == "PDF to JPG" else ".pdf"),
            "kind": "JPG image(s)" if self.mode == "PDF to JPG" else "PDF file(s)",
            "warning": warning,
        }

    def request(self):
        contract = self.contract()
        return {
            "mode": self.mode,
            "files": list(self.files),
            "contract": contract,
            "groups": self.groups() if self.mode == "Split PDF" else [],
            "combine": self.combine,
            "compression": self.compression,
            "order": list(self.order),
            "removed": list(self.removed),
            "rotations": dict(self.rotations),
            "page_size": self.page_size,
            "orientation": self.orientation,
            "margin": int(self.margin),
            "password": self.password if self.mode == "Protect PDF" else "",
            "input_password": self.input_password if self.mode == "Unlock PDF" else "",
            "watermark": self.watermark() if self.mode == "Watermark" else None,
            "page_edit": self.page_edit(),
            "jpg_pages": chosen_pages(self.target_pages, self.page_count) if self.mode == "PDF to JPG" else [],
            "jpg_dpi": int(self.jpg_dpi),
            "jpg_quality": int(self.jpg_quality),
        }
