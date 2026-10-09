# PDF Studio 1.4.1 review

No findings remain in the final source diff reviewed against `20acb370365491681fcbe4f9d133060704d2da1e`.

## Changes and evidence

- Preview work is serialized, obsolete work exits between pages, pending requests are cancelled, and generation checks still reject completions already queued. A bounded cache stores copies of PDF thumbnails. Keys include path, size, modification time, page and edit settings; authentication runs before cache access.
- A shared stamp renderer reuses identical stamp PDFs and font objects. An 80-page synthetic Unicode watermark fixture decreased from 9,673,304 bytes and 161 font objects to 182,333 bytes and 3 font objects. Three local runs gave median export times of 2.1324 seconds before and 0.2265 seconds after. Concurrent tests and system load may affect timings. The repeatable script is `benchmark_watermark.py`; raw results are in `optimization-results.json`.
- Visible text is positioned by its bounds. The former center placement was 25.568 points too high on a 400 by 500 point test page; the revised measurement is zero. The new placement test caught a cropped-page translation error during development; insertion now temporarily removes page rotation and restores it in a finally block. All four rotations and all three placements pass.
- Page selection deduplication and numbering lookups use sets/maps. JPG export releases the previous raster before allocating another; ZIP stores JPG bytes without applying another compression pass. No peak-memory measurement is claimed.

## Validation

`verify.py`, `verify_ui.py`, `verify_features.py`, `verify_extended.py` and `verify_optimizations.py` pass. Coverage includes originals preserved, save retry, process cancellation, passwords, cached-preview invalidation after source or settings changes, rapid preview replacement, 80-page numbering beyond stamp-cache capacity, rotated/cropped pages, JPG ZIP integrity, and preview/export parity.

The stale-preview journey now waits for cancellation and injects an old completion explicitly; it does not require cancelled work to emit an event.

The final windowed executable passed its packaged startup and seven worker checks. The first packaged run stopped in an exception dialog; a diagnostic build passed, and the final windowed build passed with the new smoke-report path. The diagnostic wrapper now records failures and returns a nonzero exit code; a simulated startup failure verifies this behavior. It does not change ordinary app startup. Windows installer version 1.4.1 was compiled from the final executable.

## Limits

The benchmark is one synthetic fixture on this Windows machine using Python 3.14.6 and PyMuPDF 1.28.2. Cache invalidation uses metadata, not a full file hash; a file replaced while preserving both size and timestamp can retain a stale thumbnail. A currently executing page render finishes before cancellation is observed. Large individual pages still require proportionate raster memory. Installer install/uninstall verification is not run over the user's existing installation.
