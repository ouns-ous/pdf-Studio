"""PNG export fidelity, transparency, page order and complete desktop journeys."""
import math
import multiprocessing as mp
import tempfile
import tkinter as tk
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image, ImageChops
from app import App
from jobs import execute
from pdf_workflow import Session
from verify_navigation import button
from verify_ui import pump


def labels(parent):
    result = []
    for widget in parent.winfo_children():
        if isinstance(widget, tk.Label):
            result.append(widget.cget("text"))
        result.extend(labels(widget))
    return result


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "وثيقة-é.pdf"
        with pymupdf.open() as doc:
            for rotation in (0, 90, 180, 270):
                page = doc.new_page(width=400, height=500)
                page.draw_rect(pymupdf.Rect(30, 40, 150, 180), fill=(1, 0, 0), color=None)
                page.draw_rect(pymupdf.Rect(170, 40, 240, 180), fill=(1, 1, 1), color=None)
                page.insert_text((40, 230), "KEEP TEXT AND SHAPES")
                page.set_cropbox(pymupdf.Rect(20, 30, 380, 470))
                page.set_rotation(rotation)
            doc.save(source)
        original = source.read_bytes()

        def session(**settings):
            return Session("PDF to PNG", files=[str(source)], counts=[4], loaded=True, **settings)

        def output(task, name):
            folder = root / name
            folder.mkdir()
            return execute(task.request(), folder)

        # Check rendered pixels and rotated/cropped geometry at all supported DPIs.
        for dpi in (72, 150, 300):
            for transparent in (False, True):
                task = session(png_dpi=str(dpi), png_transparent=transparent, target_pages="4,2-3,2,1")
                assert task.contract()["extension"] == ".zip"
                assert task.contract()["count"] == 4 and task.contract()["kind"] == "PNG image(s)"
                result = output(task, f"{dpi}-{transparent}")
                assert len(result["images"]) == 4 and not result["pdfs"]
                with zipfile.ZipFile(result["path"]) as archive, pymupdf.open(source) as doc:
                    assert archive.namelist() == [f"{source.stem}-page-{i:04d}.png" for i in range(1, 5)]
                    assert archive.testzip() is None
                    for index, item in enumerate(archive.infolist()):
                        assert item.compress_type == zipfile.ZIP_STORED
                        with Image.open(BytesIO(archive.read(item))) as image:
                            image.load()
                            rect = doc[index].rect
                            assert image.format == "PNG"
                            assert image.size == (math.ceil(rect.width * dpi / 72), math.ceil(rect.height * dpi / 72))
                            assert image.mode == ("RGBA" if transparent else "RGB")
                            expected = doc[index].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=transparent)
                            # PNG stores straight alpha; MuPDF samples are premultiplied.
                            pixels = image.convert("RGBa") if transparent else image
                            native = Image.frombytes(pixels.mode, pixels.size, expected.samples)
                            difference = ImageChops.difference(pixels, native).getextrema()
                            # Alpha unpremultiplication can round a color channel by 1/255.
                            assert all(high <= (1 if transparent else 0) for _, high in difference)
                            if transparent:
                                assert difference[3] == (0, 0)
                            if transparent:
                                assert image.getextrema()[3] == (0, 255)
                                if index == 0:
                                    # Unpainted page space is transparent; explicit white graphics remain opaque.
                                    assert image.getpixel((int(300*dpi/72), int(300*dpi/72)))[3] == 0
                                    assert image.getpixel((int(170*dpi/72), int(50*dpi/72))) == (255, 255, 255, 255)

        single = session(target_pages="2", png_dpi="72")
        assert single.contract()["extension"] == ".png"
        assert output(single, "single")["path"].endswith(".png")
        for settings in (dict(target_pages="5"), dict(target_pages="1,"), dict(png_dpi="0"),
                         dict(png_dpi="600"), dict(png_transparent="false")):
            try:
                session(**settings).contract()
            except ValueError:
                pass
            else:
                raise AssertionError(f"Invalid settings accepted: {settings}")
        large = root / "large.pdf"
        with pymupdf.open() as doc:
            doc.new_page(width=8000, height=8000)
            doc.save(large)
        large_task = Session("PDF to PNG", files=[str(large)], counts=[1], loaded=True, png_dpi="72")
        try:
            output(large_task, "large-output")
        except ValueError as error:
            assert "lower DPI" in str(error)
        else:
            raise AssertionError("Oversized raster was accepted")

        app = App()
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            app.show_home("Convert PDF")
            app.change("PDF to PNG")
            app.import_files([str(source)])
            pump(app)
            assert str(app.action["state"]) == "normal"
            app.feature_vars["target_pages"].set("9")
            assert str(app.action["state"]) == "disabled"
            app.feature_vars["target_pages"].set("3,1,3")
            app.feature_vars["png_dpi"].set("72")
            app.feature_vars["png_transparent"].set(True)
            assert "2 PNG image(s)" in app.validation.get()
            button(app.body, "← Back").invoke()
            assert app.home_active and app.home_category == "Convert PDF"
            app.change("PDF to PNG")
            pump(app)
            assert app.session.png_transparent and app.session.target_pages == "3,1,3"
            app.run()
            pump(app, lambda: not app.busy)
            assert app.session.result and len(app.session.result["images"]) == 2
            assert any("2 PNG image(s)" in text for text in labels(app.body))
            assert app.save_result(destination=root / "result.zip")
            app.continue_with("Images to PDF")
            pump(app)
            assert len(app.session.files) == 2 and all(path.endswith(".png") for path in app.session.files)
            assert str(app.action["state"]) == "normal"
            app.run()
            pump(app, lambda: not app.busy)
            with pymupdf.open(app.session.result["path"]) as doc:
                assert len(doc) == 2
            app.change("PDF to PNG")
            button(app.body, "← Back").invoke()
            pump(app)
            app.feature_vars["target_pages"].set("1")
            app.feature_vars["png_transparent"].set(False)
            app.run()
            pump(app, lambda: not app.busy)
            destination = root / "saved.png"
            with patch("app.filedialog.asksaveasfilename", return_value=str(destination)) as save:
                assert app.save_result()
                assert save.call_args.kwargs["defaultextension"] == ".png"
                assert save.call_args.kwargs["filetypes"] == [("PNG image", "*.png")]
            with Image.open(destination) as image:
                assert image.format == "PNG" and image.mode == "RGB"
            button(app.body, "← Back").invoke()
            pump(app)
            app.geometry("1060x680")
            app.deiconify()
            app.update()
            assert app.action.winfo_ismapped()
            assert app.action.winfo_rooty() + app.action.winfo_height() <= app.winfo_rooty() + app.winfo_height()
            button(app.body, "× Remove PDF").invoke()
            pump(app)
            assert not app.session.files and app.session.png_dpi == "150" and not app.session.png_transparent
            assert not errors, errors
        finally:
            app.destroy()
        assert source.read_bytes() == original
    print("PNG passed: pixel fidelity, alpha/white backgrounds, crop/rotation, DPI, ordered ZIPs, validation, size limit, Unicode paths, spawned UI jobs, save, continuation and navigation.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
