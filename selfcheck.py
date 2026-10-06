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
