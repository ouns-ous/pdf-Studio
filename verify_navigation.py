"""Back navigation and recovery from an accidentally selected file."""
import multiprocessing as mp
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image
from app import App
from jobs import execute
from pdf_workflow import TOOLS, BATCH
from verify_ui import pump


def button(parent, label):
    for widget in parent.winfo_children():
        if isinstance(widget, tk.Button) and widget.cget("text") == label:
            return widget
        found = button(widget, label)
        if found is not None:
            return found
    return None


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source, locked, image = root / "chosen-by-mistake.pdf", root / "locked.pdf", root / "image.png"
        with pymupdf.open() as doc:
            for i in range(3):
                page = doc.new_page()
                page.insert_text((40, 70), f"Keep original page {i+1}")
            doc.save(source)
            doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw="owner-test-pass", user_pw="input-test-pass")
        Image.new("RGB", (100, 100), "red").save(image)
        originals = {path: path.read_bytes() for path in (source, locked, image)}
        app = App()
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            # Every tool exposes Back before and after importing.
            for mode, (category, *_) in TOOLS.items():
                app.show_home(category)
                app.change(mode)
                button(app.body, "← Back").invoke()
                assert app.home_active and app.home_category == category
                app.change(mode)
                path = locked if mode == "Unlock PDF" else image if mode == "Images to PDF" else source
                with patch("app.simpledialog.askstring", return_value="input-test-pass"):
                    app.import_files([str(path)])
                pump(app)
                retained = app.session
                button(app.body, "← Back").invoke()
                assert app.home_active and app.session is retained and retained.files
                app.change(mode)
                pump(app)
                label = "× Remove image" if mode == "Images to PDF" else "× Remove PDF"
                button(app.body, label).invoke()
                pump(app)
                assert not app.session.files and not app.home_active
                assert button(app.body, "← Back") is not None
                if mode not in BATCH:
                    assert app.session.page_count == 0 and not app.session.order
                    assert not app.session.input_password and not app.session.password
            # Removing a batch card only removes that input; Undo restores it.
            app.change("Merge PDF")
            app.import_files([str(source), str(source)])
            pump(app)
            button(app.cards[0], "× Remove PDF").invoke()
            pump(app)
            assert len(app.session.files) == 1
            app.undo()
            pump(app)
            assert len(app.session.files) == 2
            # Remove still works when a page render is in progress.
            app.change("Watermark")
            app.preview_cache.clear()
            started, release = threading.Event(), threading.Event()
            thumbnail = app.thumbnail
            def blocked(page):
                started.set()
                assert release.wait(10)
                return thumbnail(page)
            with patch.object(app, "thumbnail", side_effect=blocked):
                app.import_files([str(source)])
                future = app.preview_future
                pump(app, started.is_set)
                button(app.body, "× Remove PDF").invoke()
                assert not app.loading and not app.session.files
                release.set()
                pump(app, future.done)
                assert not app.session.files
            # Result Back preserves the result. Remove honors cancel/save failure.
            app.change("PDF to JPG")
            app.import_files([str(source)])
            pump(app)
            folder = root / "result"
            folder.mkdir()
            result = app.session.result = execute(app.session.request(), folder)
            app.show_result()
            button(app.body, "← Back").invoke()
            pump(app)
            assert app.session.result is result
            with patch("app.messagebox.askyesnocancel", return_value=None):
                button(app.body, "× Remove PDF").invoke()
            assert app.session.files and app.session.result is result
            with patch("app.messagebox.askyesnocancel", return_value=True), patch.object(app, "save_result", return_value=False):
                button(app.body, "× Remove PDF").invoke()
            assert app.session.files and app.session.result is result
            with patch("app.messagebox.askyesnocancel", return_value=False):
                button(app.body, "× Remove PDF").invoke()
            assert not app.session.files and app.session.result is None
            # Both controls remain on screen at the minimum supported size.
            app.geometry("1060x680")
            app.deiconify()
            app.change("Split PDF")
            app.import_files([str(source)])
            pump(app)
            for label in ("← Back", "× Remove PDF"):
                control = button(app.body, label)
                assert control.winfo_ismapped()
                assert control.winfo_rootx() >= app.winfo_rootx()
                assert control.winfo_rootx() + control.winfo_width() <= app.winfo_rootx() + app.winfo_width()
                assert control.winfo_rooty() + control.winfo_height() <= app.winfo_rooty() + app.winfo_height()
            assert not errors, errors
        finally:
            if "release" in locals():
                release.set()
            app.destroy()
        assert all(path.read_bytes() == original for path, original in originals.items())
    print("Navigation passed: Back in all tools, category/task retention, input removal, batch Undo, loading cancellation, result protection and originals preserved.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
