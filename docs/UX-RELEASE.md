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
