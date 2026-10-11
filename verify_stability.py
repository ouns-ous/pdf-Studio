"""Recovery and preview/export regressions using only temporary synthetic inputs."""
import json
import multiprocessing as mp
import tempfile
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image
from app import App
from jobs import execute, run_job
from pdf_tools import selection, process
from pdf_workflow import Session
from source_files import SourceFileError
from verify_ui import pump
from verify_navigation import button


def make_pdf(path, pages=1, label="Original"):
    with pymupdf.open() as doc:
        for index in range(pages):
            doc.new_page(width=300, height=400).insert_text((30, 60), f"{label} {index + 1}")
        doc.save(path)


def expect_changed(request, folder, progress=lambda text: None):
    folder.mkdir()
    try:
        execute(request, folder, progress)
    except SourceFileError as error:
        assert "changed" in str(error), error
    else:
        raise AssertionError("A changed input was published as a reviewed result")


def run():
    for text in ("abc", "1,", "-", "1-", "1--2", "1.5", "1,,2"):
        try:
            selection(text, 5)
        except ValueError as error:
            assert str(error) == "Use page numbers like 1,3-5.", (text, error)
        else:
            raise AssertionError(f"Accepted invalid pages: {text}")
    assert selection(" 3, 1-2, 2 ", 3) == [2, 0, 1]

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source, other = root / "source.pdf", root / "other.pdf"
        make_pdf(source, 13)
        make_pdf(other, 2)
        other_original = other.read_bytes()
        fixtures = [
            ("rgba", Image.new("RGBA", (100, 80), (0, 0, 0, 0)), (255, 255, 255)),
            ("half-alpha", Image.new("RGBA", (100, 80), (255, 0, 0, 128)), (255, 127, 127)),
            ("grayscale-alpha", Image.new("LA", (100, 80), (0, 0)), (255, 255, 255)),
            ("palette", Image.new("P", (100, 80), 0), (255, 255, 255)),
        ]
        fixtures[-1][1].putpalette([0, 255, 0] + [0] * 765)
        fixtures[-1][1].info["transparency"] = 0
        for name, image, expected in fixtures:
            path = root / (name + ".png")
            image.save(path)
            folder = root / name
            folder.mkdir()
            request = Session("Images to PDF", files=[str(path)], counts=[1], loaded=True,
                              page_size="Original", margin="0").request()
            result = execute(request, folder)
            with pymupdf.open(result["path"]) as doc:
                pix = doc[0].get_pixmap(dpi=150)
                assert pix.pixel(50, 40) == expected, (name, pix.pixel(50, 40))
                assert len(doc) == 1 and abs(doc[0].rect.width - 48) < .01
            # The legacy converter shares alpha handling too (JPEG permits rounding).
            process("Images to PDF", [str(path)], root / (name + "-legacy.pdf"))
            with pymupdf.open(root / (name + "-legacy.pdf")) as doc:
                pix = doc[0].get_pixmap(dpi=150)
                assert all(abs(a - b) <= 3 for a, b in zip(pix.pixel(50, 40), expected))

        app = App()
        app.withdraw()
        errors = []
        app.report_callback_exception = lambda *args: errors.append(args)
        try:
            # Losing a file after previews load cannot break the gallery or event loop.
            app.change("Compress PDF")
            app.import_files([str(source), str(other)])
            pump(app)
            source.unlink()
            app.after(0, app.paint_gallery)
            heartbeat = []
            app.after(100, lambda: heartbeat.append(True))
            pump(app, lambda: bool(heartbeat))
            assert not errors, errors
            app.run()
            assert not app.busy and "missing" in app.session.errors[0]
            assert str(app.action["state"]) == "disabled" and len(app.cards) == 2
            app.remove_file(0)
            pump(app)
            assert not app.session.errors and str(app.action["state"]) == "normal"
            app.undo()
            pump(app)
            assert "missing" in app.session.errors[0]
            app.remove_file(0)
            pump(app)

            # A changed page count cannot reuse a previous page order/rotation/range.
            make_pdf(source, 13)
            app.change("Organize PDF")
            app.import_files([str(source)])
            pump(app)
            app.paginate(12)
            pump(app)
            app.rotate_page(12)
            stale = app.session.request()
            replacement = root / "replacement.pdf"
            make_pdf(replacement, 1, "Replacement")
            replacement.replace(source)
            app.run()
            assert not app.busy and "changed" in app.session.errors[0]
            assert app.session.offset == 0 and len(app.cards) == 1
            app.refresh()
            pump(app)
            assert "changed" in app.session.errors[0]
            expect_changed(stale, root / "stale-job")
            assert not list((root / "stale-job").iterdir())
            app.import_files([str(source)])
            pump(app)
            assert not app.session.errors and app.session.order == [0] and not app.session.rotations

            # Changes during processing are rejected before publishing the result.
            app.change("Merge PDF")
            app.import_files([str(source), str(other)])
            pump(app)
            reviewed = app.session.request()
            def change_during_job(message):
                make_pdf(replacement, 3, "Changed during job")
                replacement.replace(source)
            expect_changed(reviewed, root / "racing-job", change_during_job)
            folder = root / "reported-error"
            folder.mkdir()
            run_job(reviewed, folder)
            assert json.loads((folder / "status.json").read_text())['state'] == 'error'
            app.move(0, 1)
            pump(app)
            assert "changed" in app.session.errors[1] and 0 not in app.session.errors
            with patch("app.filedialog.askopenfilename", return_value=str(source)):
                button(app.cards[1], "Replace").invoke()
            pump(app)
            assert not app.session.errors
            app.undo()
            pump(app)
            assert "changed" in app.session.errors[1]

            # Transparency previews use the same preparation as the exported PDF.
            app.change("Images to PDF")
            for name, _, expected in fixtures:
                app.import_files([str(root / (name + ".png"))])
                pump(app)
                preview = dict(app.preview_data)[len(app.session.files) - 1]
                assert preview.getpixel((preview.width // 2, preview.height // 2)) == expected
            originals = {Path(path): Path(path).read_bytes() for path in app.session.files}
            app.margin_var.set("80")
            assert str(app.action["state"]) == "disabled" and "Update preview" in app.validation.get()
            app.run()
            assert not app.busy and app.session.result is None
            app.refresh()
            pump(app)
            assert str(app.action["state"]) == "normal"
            app.session.page_size = "Original"
            app.refresh()
            pump(app)
            assert all("Margins are too large" in message for message in app.session.errors.values())
            assert str(app.action["state"]) == "disabled"
            app.margin_var.set("0")
            app.refresh()
            pump(app)
            assert not app.session.errors and str(app.action["state"]) == "normal"
            app.run()
            pump(app, lambda: not app.busy)
            assert app.session.result and app.session.result["pages"] == 4
            assert all(path.read_bytes() == data for path, data in originals.items())

            # Failed saves preserve both an existing destination and the result for retry.
            destination = root / "saved.pdf"
            destination.write_bytes(b"existing destination")
            before = set(root.iterdir())
            def failed_copy(source, temporary):
                Path(temporary).write_bytes(b"partial output")
                raise OSError("Synthetic disk write failure")
            with patch("app.shutil.copyfile", side_effect=failed_copy), patch("app.messagebox.showerror"):
                assert not app.save_result(destination=destination)
            assert destination.read_bytes() == b"existing destination"
            assert not app.session.result["saved"] and set(root.iterdir()) == before
            assert app.save_result(destination=destination)
            with pymupdf.open(destination) as doc:
                assert len(doc) == 4
            # Replace keeps a batch slot and settings, supports cancellation and Undo.
            app.geometry("1060x680")
            app.deiconify()
            for mode in ("Merge PDF", "Compress PDF", "Images to PDF"):
                app.change(mode)
                app.new_task()
                images = mode == "Images to PDF"
                paths = [str(root / "rgba.png"), str(root / "palette.png")] if images else [str(other), str(source)]
                chosen = str(root / "half-alpha.png") if images else str(other)
                app.import_files(paths)
                pump(app)
                control = button(app.cards[1], "Replace")
                assert control.winfo_ismapped()
                assert control.winfo_rooty() + control.winfo_height() < app.winfo_rooty() + app.winfo_height()
                history = len(app.session.history)
                with patch("app.filedialog.askopenfilename", return_value=""):
                    control.invoke()
                assert app.session.files == paths and len(app.session.history) == history
                with patch("app.filedialog.askopenfilename", return_value=chosen):
                    control.invoke()
                pump(app)
                assert app.session.files == [paths[0], chosen]
                assert str(app.action["state"]) == "normal"
                app.undo()
                pump(app)
                assert app.session.files == paths
            assert other.read_bytes() == other_original
            assert not errors, errors
        finally:
            app.destroy()
    print("Stability passed: missing/changed inputs, worker races, Replace/Undo, alpha images, preview gating, margin validation, page errors and atomic save retry.")


if __name__ == "__main__":
    mp.freeze_support()
    run()
