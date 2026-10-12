# PDF to PNG - version 1.5.0

PDF to PNG is the fourteenth working tool, available on the Convert PDF home category and menu. It exports all pages or selected ranges at 72, 150 or 300 DPI. White is the default background; optional transparency preserves unpainted areas while keeping explicit white page graphics opaque. Existing page crops and rotations are respected. PNG compression is lossless, though raster resolution still depends on the selected DPI.

The tool follows the same choose → configure → process → save/continue journey. Multiple pages are deduplicated and saved in document order inside a ZIP; one page saves directly as PNG. Result counts and file dialogs identify PNG correctly. Results can continue into Images to PDF, where transparency is composited onto white PDF pages. Back, Remove PDF, input-change detection and retained task settings remain available.

JPG and PNG share the isolated rendering worker, with separate resolution settings per tool. The worker releases each raster before allocating the next, rejects renders larger than 40 million pixels and stores already-compressed image files directly in ZIP.

`verify_png.py` covers all supported DPIs and four rotations on cropped pages, RGB pixel equality and alpha/color fidelity (allowing one color level of rounding when converting premultiplied alpha), transparent space versus explicit white graphics, single/ZIP output, page order/deduplication, invalid settings, oversized pages and Unicode filenames. UI tests exercise spawned exports, result/save labels, continuation, retained options, Back, Remove PDF and the primary action at the minimum window size. The packaged smoke check includes a transparent PNG export.

Validation completed on 2026-10-12: all eight regression suites passed. The Windows executable matches all nine application source modules and passed startup plus nine packaged worker checks. The 1.5.0 installer compiled successfully. Installation/uninstallation was not run over the existing installation; the automated checks use synthetic documents.

---

# Stability and batch replacement - version 1.4.3

The stability audit reproduced three gaps that the existing six test suites did not cover: repainting a batch card after its source disappeared raised `FileNotFoundError`; transparent black PNG pixels became black in exported PDFs; and image margins could change without refreshing the preview before processing.

- Gallery labels use the metadata already read by the preview worker, so a disappearing source cannot interrupt the UI polling loop. Missing, inaccessible or externally changed inputs receive actionable card errors. File size, modification time and file identity are checked during previews, before processing and at worker completion. Changed inputs must be selected again before old page settings can be applied. These checks are not a file lock or a content hash.
- **Replace** on Merge, Compress and Images to PDF cards preserves the file's position. Cancelling the picker leaves the task untouched; Undo restores the old selection and its reviewed file version. Original files are never deleted by these controls.
- Transparent and partly transparent images are composited onto white using the same preparation for previews and both PDF converters. RGBA, grayscale alpha and palette transparency are covered.
- Image settings must match the current preview before processing. Original-size margins that leave no room for the image are reported before starting a job, and can be corrected in the same task. Malformed page ranges display `Use page numbers like 1,3-5.` instead of a Python conversion error.

`verify_stability.py` exercises these cases, file replacement/cancellation/Undo in all three batch tools, a source changing during processing, worker error reporting, and a partial save failure that preserves an existing destination and allows retry. Existing regression suites cover the thirteen tools, result continuation, cancellation, encryption, Unicode watermarks, cropping, numbering, page order and rotations. The packaged smoke check now includes transparent-image conversion and reviewed source metadata.

Validation on 2026-10-11: all seven regression suites passed. After adding batch replacement, the stability, navigation, user-journey and optimization suites passed again. The final Windows executable matches all nine application source modules and passed its startup/eight-worker smoke check. The 1.4.3 installer compiled successfully; installation/uninstallation was not run over the existing installation. These are automated checks on synthetic documents, not a guarantee for every PDF or a manual accessibility audit.

---

# Back and input removal - version 1.4.2

A consistent Back button now appears on the file-selection, workspace and result screens. A result returns to its settings while retaining the generated output. A tool returns to the previously selected home category and preserves its task.

Every single-PDF workspace now has a visible Remove PDF button beside Undo. It clears a mistaken input, page state and passwords, cancels pending previews and returns to file selection. Unsaved results still offer save, discard or cancel. Batch cards put Remove PDF or Remove image on a separate row, keeping the full label visible and preserving Undo. These controls never delete source files from disk.

`verify_navigation.py` checks all thirteen tools, task/category retention, individual batch removal and Undo, removal during preview loading, cancelled or failed result saving, minimum-size button visibility and unchanged source bytes. Existing user-journey and extended-tool regressions also pass.

---

# Performance update - version 1.4.1

PDF previews reuse a bounded in-memory cache and cancel superseded work. Identical watermarks reuse font resources; visible text placement is corrected for rotated and previously cropped pages. Page-selection deduplication and numbering lookup avoid repeated list scans. JPG export releases one raster before creating the next and stores JPEGs directly in ZIP.

All five regression suites pass, including the new `verify_optimizations.py`. The final windowed executable passed startup and all packaged PDF worker checks with an explicit diagnostic report. Smoke checks now record startup or worker errors and return a nonzero exit code on failure. The installer was rebuilt as version 1.4.1; installation/uninstallation was not run over the existing installation.

The 80-page synthetic watermark benchmark reduced output from 9,673,304 to 182,333 bytes. See [raw measurements](optimization-results.json), [review and limits](OPTIMIZATION-REVIEW.md) and [the design report](PDF-Studio-Performance-Review.docx). The six-page report retains the selected template's styles, layout and recurring elements; its fields and every rendered page were verified.

---

# New tools — version 1.4

Six additional tools follow the same import → configure → preview → process → save/continue journey as the existing seven:

- Protect PDF: matching password fields, optional visibility, AES-256 output, and Unlock continuation.
- Unlock PDF: password retry/cancel on import, preservation of the previous task, and an unencrypted output copy. Already unencrypted input is reported without replacing the task.
- Watermark: Unicode text, selected pages, opacity, font size and Top/Center/Bottom placement.
- PDF to JPG: selected pages in document order, DPI/quality choices, single JPG or ZIP output, and direct continuation to Images to PDF.
- Page numbers: selected pages, starting number, position and format; numbering follows document order.
- Crop PDF: percentage margins relative to the displayed page, with preview. This changes the visible crop box and does not erase hidden content.

Watermark, numbering and crop share their preview/export implementation. Editing their settings disables processing until Update preview is used. Rotation and existing crop boxes are preserved. Result labels and save formats distinguish JPGs from PDFs; the continuation picker only offers compatible tools. Passwords are held in task memory, not serialized to status or result files.

A Windows status-file race discovered during spawned-worker tests is handled with bounded retries while the UI reads progress. The build configuration explicitly locates Conda native DLLs so release builds do not depend on shell activation.

Validation: `verify_features.py` covers encryption, password mismatch/retry/cancel, selected watermark pages, rotated inputs, identical preview/export rendering, save and continuation. `verify_extended.py` covers JPG/ZIP dimensions at three DPIs, range validation, numbering, crop on previously cropped and rotated PDFs, preview parity, spawned workers, and action visibility at 1060×680. `verify.py` and `verify_ui.py` retain the original-tool regressions. `selfcheck.py` now exercises every new worker in the packaged executable, including multilingual watermark rendering.

The Windows executable passed startup and all six new spawned-worker smoke checks; the 1.4.0 installer compiled successfully. An installation/uninstallation check was skipped because PDF Studio is already installed on this machine. Synthetic rendered pages were visually inspected for multilingual watermark, numbering and crop placement; full manual UI and screen-reader audits are not claimed.

This release adds text watermarks, not image watermarks. Office conversion, OCR, freeform editing, signature, comparison and AI capabilities remain unimplemented. No manual screen-reader certification is claimed.

---

# UX fixes — version 1.3

This implements the existing-tool workflow corrections from the audit. It does not claim complete feature parity with iLovePDF.

| Audit items | Implementation |
|---|---|
| U01–U02 | Independent sessions; navigation and selecting the same tool preserve files, ranges, order, rotations and settings. |
| U03–U05 | Batch compression retains all inputs. Single-file tools say Replace PDF and reject multiple inputs. File errors remain removable cards beside valid files. |
| U06 | Organize has reorder, rotate, remove/restore and undo; Remove pages is a separate tool. |
| U07–U10 | Preview clicks do not switch Split mode. Invalid ranges disable processing, with field-specific feedback. Overlapping combined ranges keep repetitions. All split modes share the same combined/separate output choice. |
| U11–U13 | Honest compression copy, seven available tools, actual tool menus. Inactive catalogue cards removed. |
| U14–U17 | File/page dragging, order labels, sorting and keyboard arrows; compression uses file cards; deletion markers and rotation previews; native file drop integration through TkDnD. |
| U18–U20 | Temporary result first, save/retry/open/continue next. Per-file compression statistics. Isolated cancellable jobs and actionable errors. |
| U21 | Focusable home cards/controls, responsive home grid and scroll routing by the hovered canvas. Manual screen-reader certification is not claimed. |
| U22 | Fixed splitting, combined/separate page extraction, batch compression, true Organize and image page settings implemented. Office conversion, OCR, signature and other new engines remain out of scope. |

## Verification

`python verify.py` and `python verify_ui.py` pass on synthetic fixtures. The latter launches a real spawned worker and validates resulting PDF content, ZIP contents, rotation, margins, cancellation, save failure recovery and unchanged input bytes. The Windows executable passed its startup and spawned-worker smoke check, its entry-point bytecode matches the final source, and the installer compiled successfully. Layout checks confirmed the primary action remains visible at 1060×680 for Split, Organize, Compress and Rotate. Native file-drop wiring is included, but Explorer-to-app dragging was not manually verified. Native window capture was unavailable during the visual check; no claim of a completed manual visual or screen-reader audit is made.

## Retained limits

- Sessions survive navigation, not application restarts.
- Previews are paginated by 12; arrows can move a file/page across a batch boundary.
- Version 1.3 required unlocked copies; version 1.4 adds Unlock PDF.
- Images margins use points. Original page size follows the image aspect ratio.
- A multi-file result is saved as ZIP; generated PDFs are available directly to continuation tools.
- The default homepage lists supported tools only. It does not promise unavailable Office/OCR/AI actions.

The baseline in `ux-baseline.json` records the old `d029cce` behavior, not current expected results. `reproduce_ux_baseline.py` is a historical reproducer for that revision; use `verify_ui.py` for current regression checks.
