"""Security / watermark acceptance checks with synthetic documents only."""

import json
import multiprocessing as mp
import tempfile
from pathlib import Path
from unittest.mock import patch
import pymupdf
from app import App
from jobs import execute, run_job
from pdf_workflow import Session
from verify_ui import pump


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.pdf"
        with pymupdf.open() as doc:
            for i, rotation in enumerate([0, 90, 180, 270]):
                page = doc.new_page(width=400, height=500)
                page.insert_text((40, 70), f"Original page {i+1}")
                page.set_rotation(rotation)
            doc.save(source)
        original = source.read_bytes()
        password = "test-password-42"
        protect = Session("Protect PDF", files=[str(source)], counts=[4], loaded=True,
                          password=password, confirmation=password)
        protect_folder = root / "protect"
        protect_folder.mkdir()
        run_job(protect.request(), protect_folder)
        status = (protect_folder / "status.json").read_text(encoding="utf-8")
        assert password not in status
        state = json.loads(status)
        assert state["state"] == "done", state
        protected = state["result"]["path"]
        with pymupdf.open(protected) as doc:
            assert doc.needs_pass and not doc.authenticate("incorrect")
            assert doc.authenticate(password)
            assert "AES" in doc.metadata["encryption"]
            assert all(f"Original page {i+1}" in p.get_text() for i, p in enumerate(doc))
        unlock = Session("Unlock PDF", files=[protected], counts=[4], loaded=True,
                         input_password=password)
        unlock_folder = root / "unlock"
        unlock_folder.mkdir()
        result = execute(unlock.request(), unlock_folder)
        with pymupdf.open(result["path"]) as doc:
            assert not doc.needs_pass and doc.metadata["encryption"] is None
            assert [p.rotation for p in doc] == [0, 90, 180, 270]
        unlock.input_password = "wrong"
        try:
            execute(unlock.request(), unlock_folder)
            raise AssertionError("Incorrect password was accepted")
        except ValueError:
            pass
        for position in ["Top", "Center", "Bottom"]:
            stamp = Session("Watermark", files=[str(source)], counts=[4], loaded=True,
                            watermark_text="PRIVATE & <draft>", watermark_pages="2-4",
                            watermark_position=position)
            folder = root / position
            folder.mkdir()
            result = execute(stamp.request(), folder)
            with pymupdf.open(result["path"]) as doc, pymupdf.open(source) as before:
                assert doc[0].get_pixmap().samples == before[0].get_pixmap().samples
                for i in range(1, 4):
                    assert "PRIVATE & <draft>" in doc[i].get_text()
                    assert f"Original page {i+1}" in doc[i].get_text()
                    assert doc[i].rect == before[i].rect
                    assert doc[i].get_pixmap().samples != before[i].get_pixmap().samples
        for key, value in [("watermark_pages", "5"), ("watermark_opacity", "0"),
                           ("watermark_size", "abc"), ("watermark_text", "")]:
            bad = Session("Watermark", files=[str(source)], counts=[4], loaded=True)
            setattr(bad, key, value)
            try:
                bad.contract()
                raise AssertionError(f"Invalid {key} accepted")
            except ValueError:
                pass
        app = App()
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            app.change("Protect PDF")
            app.import_files([str(source)])
            pump(app)
            assert str(app.action["state"]) == "disabled"
            app.password_entries[0]._var.set(password)
            app.password_entries[1]._var.set("different")
            assert str(app.action["state"]) == "disabled"
            app.password_entries[1]._var.set(password)
            assert str(app.action["state"]) == "normal"
            # Run the real spawned worker through the UI and continue to Unlock.
            app.run()
            pump(app, lambda: not app.busy)
            assert app.session.result
            with patch("app.simpledialog.askstring", return_value=password):
                app.continue_with("Unlock PDF")
            pump(app)
            assert not app.session.errors and len(app.cards) == 4
            retained = app.session
            with patch("app.simpledialog.askstring", return_value=None):
                app.import_files([protected])
            assert app.session is retained
            with patch("app.simpledialog.askstring", side_effect=["wrong", password]), \
                 patch("app.messagebox.showerror") as error:
                app.import_files([protected])
            pump(app)
            assert error.call_count == 1 and not app.session.errors
            app.run()
            pump(app, lambda: not app.busy)
            assert app.session.result
            app.continue_with("Watermark")
            pump(app)
            app.watermark_vars["watermark_text"].set("DRAFT")
            assert str(app.action["state"]) == "disabled"
            app.refresh()
            pump(app)
            assert str(app.action["state"]) == "normal"
            preview = dict(app.preview_data)[1]
            app.run()
            pump(app, lambda: not app.busy)
            with pymupdf.open(app.session.result["path"]) as doc:
                assert preview.tobytes() == app.thumbnail(doc[1]).tobytes()
            assert app.save_result(destination=root / "saved.pdf")
            assert not errors, errors
        finally:
            app.destroy()
        assert source.read_bytes() == original
    print("Security and watermark passed: encryption, passwords, output content, rotations, ranges, preview parity, UI recovery, save and continuation.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
