"""User-journey regressions. Uses synthetic files and isolated job directories."""

import multiprocessing as mp
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from io import BytesIO
import pymupdf
from PIL import Image
from pypdf import PdfReader
from app import App
from pdf_workflow import Session
from jobs import execute
from pdf_tools import split_ranges


def pump(app, condition=None):
    condition = condition or (lambda: not app.loading)
    deadline = time.monotonic() + 30
    while not condition():
        app.update()
        if time.monotonic() > deadline:
            raise AssertionError("Timed out: " + app.status.get())
        time.sleep(0.01)
    app.update()


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        paths = []
        for name in ["A", "B"]:
            source = root / (name + ".pdf")
            with pymupdf.open() as doc:
                for i in range(15):
                    page = doc.new_page(width=300 + i * 10, height=400)
                    page.insert_text((30, 60), f"{name} page {i+1}")
                doc.save(source)
            paths.append(str(source))
        originals = [Path(p).read_bytes() for p in paths]
        app = App()
        app.withdraw()
        callback_errors = []
        app.report_callback_exception = lambda *args: callback_errors.append(args)
        try:
            app.change("Merge PDF")
            app.import_files(paths)
            pump(app)
            assert len(app.cards) == 2 and str(app.action["state"]) == "normal"
            app.move(0, 1)
            pump(app)
            assert app.session.files == paths[::-1]
            app.change("Compress PDF")
            app.import_files(paths)
            pump(app)
            assert len(app.cards) == 2 and app.session.contract()["count"] == 2
            app.change("Merge PDF")
            pump(app)
            assert app.session.files == paths[::-1]
            app.undo()
            pump(app)
            assert app.session.files == paths
            bad = root / "bad.pdf"
            bad.write_text("not a PDF")
            app.import_files([str(bad)])
            pump(app)
            assert len(app.cards) == 3 and app.session.errors == {
                2: "Cannot read this file. Remove it or choose a valid PDF."
            }
            assert str(app.action["state"]) == "disabled"
            app.remove_file(2)
            pump(app)
            assert not app.session.errors
            # Single-file imports reject excess inputs instead of dropping them.
            app.change("Split PDF")
            with patch("app.messagebox.showinfo") as info:
                app.import_files(paths)
            assert info.called and app.session.files == []
            app.import_files(paths[:1])
            pump(app)
            app.range_vars[0][0].set("3")
            app.range_vars[0][1].set("1")
            assert (
                str(app.action["state"]) == "disabled"
                and "Range 1" in app.validation.get()
            )
            app.range_vars[0][0].set("2")
            app.range_vars[0][1].set("2")
            app.toggle(0)
            assert app.session.split_mode == "Custom"
            app.change("Split PDF")
            pump(app)
            assert app.session.ranges == [("2", "2")]
            app.set_split("Pages")
            app.pages_var.set("1,3-5")
            assert (
                app.session.selected == {0, 2, 3, 4}
                and app.session.contract()["count"] == 4
            )
            app.combine_var.set(True)
            assert app.session.contract()["count"] == 1
            app.toggle(0)
            assert app.session.selected == {2, 3, 4}
            app.paginate(12)
            pump(app)
            assert set(app.cards) == {12, 13, 14}
            app.toggle(14)
            assert app.session.selected == {2, 3, 4, 14}
            app.change("Organize PDF")
            app.import_files(paths[:1])
            pump(app)
            app.move(0, 1)
            pump(app)
            assert app.session.order[:3] == [1, 0, 2]
            app.rotate_page(1)
            app.mark_removed(2)
            assert app.session.rotations[1] == 90 and app.session.removed == {2}
            folder = root / "organize"
            folder.mkdir()
            result = execute(app.session.request(), folder)
            reader = PdfReader(result["path"])
            assert len(reader.pages) == 14 and reader.pages[0].rotation == 90
            assert "A page 2" in reader.pages[0].extract_text()
            app.undo()
            pump(app)
            assert app.session.removed == set() and app.session.rotations[1] == 90
            app.change("Remove pages")
            app.import_files(paths[:1])
            pump(app)
            for i in range(15):
                app.mark_removed(i)
            assert str(app.action["state"]) == "disabled"
            app.restore_all()
            app.mark_removed(1)
            assert app.session.contract()["pages"] == 14
            # Stale preview completions cannot rebuild the home screen.
            app.refresh()
            old_generation, old_future = app.generation, app.preview_future
            app.show_home()
            pump(app, lambda: old_future.done())
            assert app.preview_cancel.is_set()
            # Even a completion already queued before cancellation is ignored.
            app.events.put(("preview", old_generation, [15], {}, [], None))
            pump(app, lambda: app.events.empty())
            assert app.home_active
            # Real spawned processing, result retention, save retry and continuation.
            app.change("Merge PDF")
            pump(app)
            app.run()
            pump(app, lambda: not app.busy)
            assert (
                app.session.result
                and len(PdfReader(app.session.result["path"]).pages) == 30
            )
            with patch("app.messagebox.showerror") as error:
                assert not app.save_result(destination=root / "missing" / "result.pdf")
                assert error.called and Path(app.session.result["path"]).exists()
                assert not app.save_result(destination=paths[0])
            assert app.save_result(destination=root / "saved.pdf")
            with patch("app.messagebox.askyesno", return_value=True):
                app.continue_with("Compress PDF")
            pump(app)
            assert app.session.page_count == 30
            # Cancel happens in an isolated worker; no destination has been requested.
            app.run()
            app.cancel_job()
            pump(app)
            assert not app.busy and len(app.session.files) == 1
            assert callback_errors == [], callback_errors
        finally:
            app.destroy()
        # Fixed ranges, overlapping ranges, separate vs combined extraction.
        s = Session(
            "Split PDF",
            files=paths[:1],
            counts=[15],
            loaded=True,
            split_mode="Fixed",
            fixed="6",
        )
        assert [len(g) for g in s.groups()] == [6, 6, 3]
        folder = root / "fixed"
        folder.mkdir()
        result = execute(s.request(), folder)
        with zipfile.ZipFile(result["path"]) as archive:
            assert [
                len(PdfReader(BytesIO(archive.read(n))).pages)
                for n in archive.namelist()
            ] == [6, 6, 3]
        s.split_mode = "Custom"
        s.ranges = [("1", "2"), ("2", "3")]
        s.combine = True
        folder = root / "overlap"
        folder.mkdir()
        result = execute(s.request(), folder)
        assert [p.extract_text().strip() for p in PdfReader(result["path"]).pages] == [
            "A page 1",
            "A page 2",
            "A page 2",
            "A page 3",
        ]
        assert split_ranges(paths[0], root / "legacy.pdf", [(1, 2), (2, 3)], True) == 4
        s.split_mode = "Pages"
        s.page_text = "1,3-5"
        s.combine = False
        folder = root / "pages"
        folder.mkdir()
        result = execute(s.request(), folder)
        assert len(result["pdfs"]) == 4
        # Batch compression processes every input and reports actual byte sizes.
        s = Session("Compress PDF", files=paths, counts=[15, 15], loaded=True)
        folder = root / "compress"
        folder.mkdir()
        result = execute(s.request(), folder)
        assert len(result["pdfs"]) == len(result["stats"]) == 2
        assert all(row["after"] <= row["before"] for row in result["stats"])
        image = root / "sample.png"
        Image.new("RGB", (500, 300), "red").save(image)
        s = Session(
            "Images to PDF",
            files=[str(image)],
            counts=[1],
            loaded=True,
            orientation="Landscape",
            margin="30",
        )
        folder = root / "image"
        folder.mkdir()
        result = execute(s.request(), folder)
        with pymupdf.open(result["path"]) as doc:
            assert doc[0].rect.width > doc[0].rect.height
            assert doc[0].get_image_info()[0]["bbox"][0] >= 29
        assert [Path(p).read_bytes() for p in paths] == originals
    print(
        "UX journeys passed: sessions, import recovery, ranges, extraction, organize, undo, batch compression, save/retry, continuation, cancellation and original preservation."
    )


if __name__ == "__main__":
    mp.freeze_support()
    run()
