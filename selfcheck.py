"""Packaged smoke check for spawn, PDF dependencies and the result contract."""

import json
import multiprocessing as mp
import tempfile
from pathlib import Path
import pymupdf
from jobs import run_job
from pdf_workflow import Session


def check_worker():
    with tempfile.TemporaryDirectory(prefix="pdf-studio-check-") as folder:
        source = Path(folder) / "sample.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((40, 60), "PDF Studio smoke check")
            doc.save(source)
        session = Session(
            "Merge PDF", files=[str(source), str(source)], counts=[1, 1], loaded=True
        )
        worker = mp.get_context("spawn").Process(
            target=run_job, args=(session.request(), folder)
        )
        worker.start()
        worker.join(40)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            raise RuntimeError("Packaged PDF worker timed out.")
        if worker.exitcode != 0:
            raise RuntimeError(f"PDF worker failed: {worker.exitcode}")
        state = json.loads((Path(folder) / "status.json").read_text(encoding="utf-8"))
        if state["state"] != "done":
            raise RuntimeError(state)
        with pymupdf.open(state["result"]["path"]) as doc:
            assert len(doc) == 2
            assert all("PDF Studio smoke check" in page.get_text() for page in doc)

        for mode in ("Protect PDF", "Unlock PDF", "Watermark", "PDF to JPG", "Page numbers", "Crop PDF"):
            output_folder = Path(folder) / mode.replace(" ", "-")
            output_folder.mkdir()
            item = Session(mode, files=[protected if mode == "Unlock PDF" else str(source)],
                           counts=[1], loaded=True, password="smoke-test-pass", confirmation="smoke-test-pass",
                           input_password="smoke-test-pass", watermark_text="DRAFT سري")
            worker = mp.get_context("spawn").Process(target=run_job, args=(item.request(), str(output_folder)))
            worker.start()
            worker.join(40)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                raise RuntimeError("Packaged feature worker timed out: " + mode)
            state = json.loads((output_folder / "status.json").read_text(encoding="utf-8"))
            assert worker.exitcode == 0 and state["state"] == "done", (mode, state)
            result = state["result"]["path"]
            if mode == "Protect PDF":
                protected = result
            if mode != "PDF to JPG":
                with pymupdf.open(result) as doc:
                    if mode == "Protect PDF":
                        assert doc.needs_pass and doc.authenticate("smoke-test-pass")
                    assert len(doc) == 1
                    if mode == "Watermark":
                        assert "DRAFT" in doc[0].get_text()
            else:
                from PIL import Image
                with Image.open(result) as image:
                    assert image.format == "JPEG" and image.width > 0


def run_smoke_check(app_factory, report_path):
    """Return a useful result even when a windowed executable has no stderr."""
    import traceback
    report = Path(report_path)
    state = {"state": "running", "phase": "startup"}
    report.write_text(json.dumps(state), encoding="utf-8")
    app = None
    try:
        app = app_factory()
        app.withdraw()
        app.update()
        app.destroy()
        app = None
        state["phase"] = "PDF workers"
        report.write_text(json.dumps(state), encoding="utf-8")
        check_worker()
        state = {"state": "passed", "phase": "complete"}
    except Exception:
        state = {"state": "failed", "phase": state["phase"],
                 "error": traceback.format_exc()}
    finally:
        if app is not None:
            try:
                app.destroy()
            except Exception:
                pass
        report.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return 0 if state["state"] == "passed" else 1
