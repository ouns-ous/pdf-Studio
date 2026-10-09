"""Small reproducible watermark benchmark; timings are local, not a guarantee."""
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
import pymupdf
from jobs import execute
from pdf_workflow import Session


def benchmark():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.pdf"
        with pymupdf.open() as doc:
            for i in range(80):
                page = doc.new_page(width=400, height=500)
                page.insert_text((35, 70), f"Original page {i+1}")
            doc.save(source)
        session = Session("Watermark", files=[str(source)], counts=[80], loaded=True,
                          watermark_text="DRAFT سري")
        timings = []
        for repeat in range(3):
            folder = root / str(repeat)
            folder.mkdir()
            start = time.perf_counter()
            result = execute(session.request(), folder)
            timings.append(time.perf_counter() - start)
        with pymupdf.open(result["path"]) as doc:
            font_count = len({f[0] for p in doc for f in p.get_fonts(full=True)})
            assert len(doc) == 80 and all("DRAFT" in p.get_text() for p in doc)
        session.watermark_text = "DRAFT"
        folder = root / "placement"
        folder.mkdir()
        centered = execute(session.request(), folder)
        with pymupdf.open(centered["path"]) as doc:
            bbox = doc[0].search_for("DRAFT")[0]
            error = abs((bbox.y0 + bbox.y1)/2 - doc[0].rect.height/2)
        return dict(pages=80, text=session.watermark_text + " سري", python=platform.python_version(),
                    pymupdf=pymupdf.VersionBind, input_bytes=source.stat().st_size,
                    output_bytes=Path(result["path"]).stat().st_size, unique_font_objects=font_count,
                    seconds=[round(n, 4) for n in timings], median_seconds=round(statistics.median(timings), 4),
                    center_error_points=round(error, 4))


if __name__ == "__main__":
    print(json.dumps(benchmark(), ensure_ascii=True, indent=2))
