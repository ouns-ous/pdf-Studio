"""Regressions for bounded previews, cancellation and reusable text stamps."""
import json
import multiprocessing as mp
import os
import tempfile
import threading
import zipfile
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image
from app import App
from jobs import execute
from pdf_features import StampRenderer, stamp_page
from pdf_tools import selection
from pdf_workflow import Session
from preview_cache import PreviewCache
from selfcheck import run_smoke_check
from verify_ui import pump


def make_pdf(path, count=13, label="Original"):
    with pymupdf.open() as doc:
        for i in range(count):
            page = doc.new_page(width=400, height=500)
            page.insert_text((35, 70), f"{label} page {i+1}")
        doc.save(path)


def run():
    cache = PreviewCache(capacity=2)
    original = Image.new("RGB", (4, 4), "white")
    cache.put("a", original)
    original.putpixel((0, 0), (0, 0, 0))
    cached = cache.get("a")
    assert cached.getpixel((0, 0)) == (255, 255, 255)
    cached.putpixel((0, 0), (1, 2, 3))
    assert cache.get("a").getpixel((0, 0)) == (255, 255, 255)
    cache.put("b", original)
    cache.get("a")
    cache.put("c", original)
    assert cache.get("b") is None and cache.get("a") is not None
    assert selection("3-5,1-4,5", 5) == [2, 3, 4, 0, 1]
    assert selection("1-50000,1-50000", 50000) == list(range(50000))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        report = root / "failed-smoke.json"
        def failed_startup():
            raise RuntimeError("synthetic startup failure")
        assert run_smoke_check(failed_startup, report) == 1
        failure = json.loads(report.read_text(encoding="utf-8"))
        assert failure["state"] == "failed" and failure["phase"] == "startup"
        assert "synthetic startup failure" in failure["error"]
        source = root / "source.pdf"
        make_pdf(source)
        app = App()
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            with patch.object(app, "thumbnail", wraps=app.thumbnail) as render:
                app.change("Organize PDF")
                app.import_files([str(source)])
                pump(app)
                assert render.call_count == 12
                first = dict(app.preview_data)[0].tobytes()
                app.paginate(12)
                pump(app)
                assert render.call_count == 13
                app.paginate(-12)
                pump(app)
                assert render.call_count == 13
                assert dict(app.preview_data)[0].tobytes() == first
                old_stat = source.stat()
                replacement = root / "replacement.pdf"
                make_pdf(replacement, label="Changed content")
                replacement.replace(source)
                os.utime(source, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns + 1_000_000))
                app.refresh()
                pump(app)
                assert render.call_count == 25
                assert dict(app.preview_data)[0].tobytes() != first
                app.change("Watermark")
                app.import_files([str(source)])
                pump(app)
                stamped = dict(app.preview_data)[0].tobytes()
                calls = render.call_count
                app.refresh()
                pump(app)
                assert render.call_count == calls
                app.watermark_vars["watermark_text"].set("CHANGED WATERMARK")
                app.refresh()
                pump(app)
                assert render.call_count == calls + 12
                assert dict(app.preview_data)[0].tobytes() != stamped
            # Hold one raster in progress, queue replacements, then leave the tool.
            app.preview_cache.clear()
            started, release = threading.Event(), threading.Event()
            real_thumbnail = app.thumbnail
            def blocked(page):
                started.set()
                assert release.wait(10), "Preview test did not release the renderer"
                return real_thumbnail(page)
            with patch.object(app, "thumbnail", side_effect=blocked) as render:
                app.refresh()
                first_future = app.preview_future
                pump(app, started.is_set)
                queued = []
                for _ in range(3):
                    app.refresh()
                    queued.append(app.preview_future)
                app.show_home()
                release.set()
                pump(app, first_future.done)
                assert render.call_count == 1
                assert all(future.cancelled() for future in queued)
                assert app.home_active and not app.loading
            assert not errors, errors
        finally:
            if "release" in locals():
                release.set()
            app.destroy()
        # Visible text placement remains correct after rotation and an existing crop.
        for position in ("Top", "Center", "Bottom"):
            with pymupdf.open() as doc, StampRenderer() as stamps:
                for rotation in (0, 90, 180, 270):
                    page = doc.new_page(width=400, height=500)
                    page.set_cropbox(pymupdf.Rect(20, 30, 380, 470))
                    page.set_rotation(rotation)
                    stamp_page(page, dict(text="DRAFT", size=36, opacity=30, position=position), stamps)
                    bounds = pymupdf.Rect(page.get_text("blocks")[0][:4]) * page.rotation_matrix
                    assert abs((bounds.x0 + bounds.x1)/2 - page.rect.width/2) < .1
                    if position == "Center":
                        assert abs((bounds.y0 + bounds.y1)/2 - page.rect.height/2) < .1
                    elif position == "Top":
                        assert abs(bounds.y0 - 20) < .1
                    else:
                        assert abs(bounds.y1 - (page.rect.height - 20)) < .1
        many = root / "many.pdf"
        make_pdf(many, 80)
        for mode in ("Watermark", "Page numbers"):
            folder = root / mode
            folder.mkdir()
            session = Session(mode, files=[str(many)], counts=[80], loaded=True,
                              watermark_text="DRAFT سري", number_style="Page n of total")
            result = execute(session.request(), folder)
            with pymupdf.open(result["path"]) as doc:
                assert len(doc) == 80
                for i, page in enumerate(doc):
                    assert f"Original page {i+1}" in page.get_text()
                    assert ("DRAFT" if mode == "Watermark" else f"Page {i+1} of 80") in page.get_text()
                if mode == "Watermark":
                    fonts = {font[0] for page in doc for font in page.get_fonts(full=True)}
                    assert len(fonts) <= 4, len(fonts)
                    assert Path(result["path"]).stat().st_size < 400_000
        jpg_folder = root / "jpg"
        jpg_folder.mkdir()
        result = execute(Session("PDF to JPG", files=[str(source)], counts=[13], loaded=True,
                                 target_pages="1-2", jpg_dpi="72").request(), jpg_folder)
        with zipfile.ZipFile(result["path"]) as archive:
            assert len(archive.infolist()) == 2
            assert all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist())
            assert archive.testzip() is None
    print("Optimizations passed: cache reuse/invalidation/eviction, cancellation, stamp placement/reuse, 80-page numbering, selection and JPG archives.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
