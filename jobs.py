"""Process-isolated jobs: cancellation can never leave a partial user file."""

import json
import os
import time
import zipfile
from pathlib import Path
from io import BytesIO
import pymupdf
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from pdf_tools import process
from pdf_features import authenticate, apply_page_edit, validate_password, StampRenderer
from pdf_workflow import PAGE_EDITS


def image_page_size(image, size, orientation):
    width, height = {"A4": (595.28, 841.89), "Letter": (612, 792)}.get(
        size, (image.width * 72 / 150, image.height * 72 / 150)
    )
    if size != "Original":
        width, height = sorted((width, height), reverse=orientation == "Landscape")
    return width, height


def export_pages(source, output, indices, rotations=None):
    reader, writer = PdfReader(source), PdfWriter()
    for index in indices:
        # Clone every occurrence independently so overlapping ranges are preserved.
        writer.add_page(reader.pages[index])
        rotation = (rotations or {}).get(index, 0)
        if rotation:
            writer.pages[-1].rotate(rotation)
    if not writer.pages:
        raise ValueError("Keep at least one page.")
    writer.write(output)
    writer.close()


def execute(request, folder, progress=lambda text: None):
    folder = Path(folder)
    mode, files = request["mode"], request["files"]
    results, stats = [], []
    if mode == "Compress PDF":
        for index, source in enumerate(files, 1):
            progress(f"Compressing file {index} of {len(files)}…")
            output = folder / f"{index:02d}-{Path(source).stem}-compressed.pdf"
            process(mode, [source], output, compression=request["compression"])
            before, after = Path(source).stat().st_size, output.stat().st_size
            stats.append({"name": Path(source).name, "before": before, "after": after})
            results.append(output)
    elif mode == "Split PDF":
        groups = request["groups"]
        if request["combine"]:
            groups = [[i for group in groups for i in group]]
        for index, group in enumerate(groups, 1):
            progress(f"Creating PDF {index} of {len(groups)}…")
            output = folder / f"{Path(files[0]).stem}-part-{index:02d}.pdf"
            export_pages(files[0], output, group)
            results.append(output)
    elif mode in ("Organize PDF", "Remove pages", "Rotate PDF"):
        progress("Applying page changes…")
        output = folder / f"{Path(files[0]).stem}-edited.pdf"
        export_pages(
            files[0],
            output,
            [i for i in request["order"] if i not in request["removed"]],
            request["rotations"],
        )
        results.append(output)
    elif mode == "Images to PDF":
        output = folder / "images.pdf"
        with pymupdf.open() as doc:
            for index, filename in enumerate(files, 1):
                progress(f"Converting image {index} of {len(files)}…")
                with Image.open(filename) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    width, height = image_page_size(
                        image, request["page_size"], request["orientation"]
                    )
                    margin = request["margin"]
                    if width <= margin * 2 or height <= margin * 2:
                        raise ValueError(
                            "Margins are too large for the original image size. Choose A4 or smaller margins."
                        )
                    data = BytesIO()
                    image.save(data, format="PNG")
                    page = doc.new_page(width=width, height=height)
                    page.insert_image(
                        pymupdf.Rect(margin, margin, width - margin, height - margin),
                        stream=data.getvalue(),
                        keep_proportion=True,
                    )
            doc.save(output, deflate=True)
        results.append(output)
    elif mode == "PDF to JPG":
        with pymupdf.open(files[0]) as doc:
            authenticate(doc, "")
            for index in request["jpg_pages"]:
                progress(f"Exporting page {index + 1} of {len(doc)}…")
                page = doc[index]
                scale = request["jpg_dpi"] / 72
                if page.rect.width * page.rect.height * scale * scale > 40_000_000:
                    raise ValueError(f"Page {index + 1} is too large at this resolution. Choose a lower DPI.")
                output = folder / f"{Path(files[0]).stem}-page-{index+1:04d}.jpg"
                pixmap = page.get_pixmap(dpi=request["jpg_dpi"], colorspace=pymupdf.csRGB, alpha=False)
                pixmap.save(output, jpg_quality=request["jpg_quality"])
                del pixmap  # Release this page before allocating the next raster.
                results.append(output)
    elif mode in {"Protect PDF", "Unlock PDF"} | PAGE_EDITS:
        output = folder / f"{Path(files[0]).stem}-{mode.lower().replace(' ', '-')}.pdf"
        with pymupdf.open(files[0]) as doc:
            authenticate(doc, request.get("input_password", ""))
            if mode == "Protect PDF":
                password = request["password"]
                validate_password(password, password)
                progress("Protecting your PDF…")
                doc.save(output, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                         user_pw=password, owner_pw=password, deflate=True)
            else:
                if mode in PAGE_EDITS:
                    settings = request["page_edit"]
                    positions = {number: rank for rank, number in enumerate(settings["indices"])}
                    with StampRenderer() as stamps:
                        for index in settings["indices"]:
                            progress(f"Applying changes to page {index + 1} of {len(doc)}…")
                            apply_page_edit(doc[index], mode, settings, stamps, positions)
                else:
                    progress("Removing PDF encryption…")
                doc.save(output, encryption=pymupdf.PDF_ENCRYPT_NONE, deflate=True)
        results.append(output)
    elif mode == "Merge PDF":
        progress("Merging your PDF files…")
        output = folder / "merged.pdf"
        process("Merge PDF", files, output)
        results.append(output)
    else:
        raise ValueError("Choose a supported PDF tool.")
    if len(results) > 1:
        output = folder / (mode.lower().replace(" ", "-") + ".zip")
        with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED if mode == "PDF to JPG" else zipfile.ZIP_DEFLATED) as archive:
            for item in results:
                archive.write(item, item.name)
    else:
        output = results[0]
    return {
        "path": str(output),
        "files": [str(item) for item in results],
        "pdfs": [str(item) for item in results if item.suffix == ".pdf"],
        "images": [str(item) for item in results if item.suffix == ".jpg"],
        "stats": stats,
        "pages": request["contract"]["pages"],
        "saved": "",
        "mode": mode,
    }


def run_job(request, folder):
    def report(payload):
        temporary = Path(folder) / "status-writing.json"
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        # Windows can briefly deny replacement while the UI is reading status.
        for attempt in range(50):
            try:
                os.replace(temporary, Path(folder) / "status.json")
                break
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.02)

    try:
        result = execute(
            request, folder, lambda text: report({"state": "working", "message": text})
        )
        report({"state": "done", "result": result})
    except Exception as error:
        report({"state": "error", "message": str(error)})
