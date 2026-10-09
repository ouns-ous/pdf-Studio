"""PDF-to-JPG, numbering and crop output and UI acceptance checks."""
import math
import multiprocessing as mp
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
import pymupdf
from PIL import Image
from app import App
from jobs import execute
from pdf_workflow import Session
from verify_ui import pump


def run():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source = root / "source.pdf"
        with pymupdf.open() as doc:
            for i, rotation in enumerate([0, 90, 180, 270]):
                page = doc.new_page(width=400, height=500)
                page.draw_rect(pymupdf.Rect(0, 0, 400, 500), color=(1,0,0), width=8)
                page.insert_text((140, 250), f"KEEP CONTENT {i+1}")
                page.set_cropbox(pymupdf.Rect(20, 30, 380, 470))
                page.set_rotation(rotation)
            doc.save(source)
        original = source.read_bytes()
        def output(session, name):
            dest = root / name
            dest.mkdir()
            return execute(session.request(), dest)
        def session(mode, **kwargs):
            return Session(mode, files=[str(source)], counts=[4], loaded=True, **kwargs)
        jpg = session("PDF to JPG", target_pages="4,2", jpg_dpi="72")
        assert jpg.contract()["extension"] == ".zip"
        result = output(jpg, "jpg")
        assert len(result["images"]) == 2 and not result["pdfs"]
        with zipfile.ZipFile(result["path"]) as archive:
            assert archive.namelist() == ["source-page-0002.jpg", "source-page-0004.jpg"]
            for name in archive.namelist():
                with archive.open(name) as handle, Image.open(handle) as image:
                    assert image.size == (440, 360) and image.mode == "RGB"
        jpg.target_pages = "1"
        result = output(jpg, "single")
        assert result["path"].endswith(".jpg")
        for dpi in (150, 300):
            jpg.jpg_dpi = str(dpi)
            result = output(jpg, "dpi" + str(dpi))
            with Image.open(result["path"]) as image:
                assert image.size == (math.ceil(360*dpi/72), math.ceil(440*dpi/72))
        numbered = session("Page numbers", target_pages="4,2-3", number_start="5", number_style="Page n of total")
        result = output(numbered, "numbers")
        with pymupdf.open(result["path"]) as doc, pymupdf.open(source) as before:
            assert doc[0].get_pixmap().samples == before[0].get_pixmap().samples
            for i in range(1,4):
                assert f"Page {i+4} of 7" in doc[i].get_text()
                assert doc[i].rect == before[i].rect
        cropped = session("Crop PDF", crop_left="10", crop_top="5", crop_right="15", crop_bottom="20")
        result = output(cropped, "cropped")
        with pymupdf.open(result["path"]) as doc, pymupdf.open(source) as before:
            for i in range(4):
                assert abs(doc[i].rect.width - before[i].rect.width * .75) < .01
                assert abs(doc[i].rect.height - before[i].rect.height * .75) < .01
                assert "KEEP CONTENT" in doc[i].get_text()
        for mode, kwargs in [("Crop PDF", dict(crop_left="80", crop_right="20")),
                             ("Page numbers", dict(number_start="0")),
                             ("PDF to JPG", dict(target_pages="7")),
                             ("PDF to JPG", dict(jpg_dpi="999"))]:
            try:
                session(mode, **kwargs).contract()
                raise AssertionError("Invalid settings accepted")
            except ValueError:
                pass
        app = App()
        app.withdraw()
        callback_errors=[]
        app.report_callback_exception=lambda *args: callback_errors.append(args)
        try:
            for mode in ("PDF to JPG", "Page numbers", "Crop PDF"):
                app.change(mode)
                app.import_files([str(source)])
                pump(app)
                assert str(app.action["state"]) == "normal", app.validation.get()
                if mode == "PDF to JPG":
                    app.feature_vars["target_pages"].set("2,4")
                else:
                    key = "number_start" if mode == "Page numbers" else "crop_left"
                    app.feature_vars[key].set("10")
                    assert str(app.action["state"]) == "disabled"
                    app.refresh()
                    pump(app)
                    preview = dict(app.preview_data)[1]
                app.run()
                pump(app, lambda: not app.busy)
                assert app.session.result
                result = app.session.result
                if mode == "PDF to JPG":
                    assert len(result["images"]) == 2
                    app.continue_with("Images to PDF")
                    pump(app)
                    assert len(app.cards) == 2 and app.session.contract()["pages"] == 2
                else:
                    with pymupdf.open(result["path"]) as doc:
                        assert app.thumbnail(doc[1]).tobytes() == preview.tobytes()
                    assert app.save_result(destination=root / (mode + ".pdf"))
            # Every tool keeps its primary action on screen at the minimum size.
            app.geometry("1060x680")
            app.deiconify()
            for mode in ("Protect PDF", "Unlock PDF", "Watermark", "PDF to JPG", "Page numbers", "Crop PDF"):
                app.change(mode)
                if not app.session.files:
                    if mode == "Unlock PDF":
                        app.sessions[mode] = session(mode)
                        app.refresh()
                    else:
                        app.import_files([str(source)])
                elif app.session.result:
                    app.refresh()
                pump(app)
                assert app.action.winfo_rooty() + app.action.winfo_height() <= app.winfo_rooty() + app.winfo_height()
            assert not callback_errors, callback_errors
        finally:
            app.destroy()
        assert source.read_bytes() == original
    print("Extended tools passed: JPG/ZIP dimensions, ranges, rotated cropped pages, numbering, input validation, previews, spawned jobs, save and image continuation.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
