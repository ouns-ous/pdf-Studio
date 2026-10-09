# PDF Studio 1.4

A local Windows PDF app with thirteen working tools: Merge, Split, Compress, Organize, Remove pages, Rotate, Images to PDF, Protect, Unlock, Watermark, PDF to JPG, Page numbers and Crop PDF.

## Install or run

- Install: `dist/PDF-Studio-Setup.exe` (per-user installation; no administrator rights or Python required).
- Portable: `dist/PDF-Studio.exe`.
- Develop: `python -m pip install -r requirements.txt`, then `python app.py`.

## Your workflow

Choose an available tool, select or drop files, review the previews and output summary, then process. Each tool keeps its own files and settings while the app remains open. Use **New task** to reset explicitly.

The result screen lets you save, open, reveal the folder, change settings, or continue with the generated PDFs in another tool. Processing happens in a temporary directory. Cancel stops the isolated worker without writing a partial file to your chosen destination. Closing or replacing an unsaved result asks you to save or discard it. Task state is not persisted across app restarts.

- **Merge:** add/remove files, drag to reorder, move with arrows or Alt+Left/Right, sort by filename, undo.
- **Split:** Custom ranges, Fixed pages per file, or individual Pages. Choose one combined PDF or separate PDFs. Multiple outputs are bundled in ZIP; one output is a PDF. Overlapping combined ranges preserve repeated pages in range order.
- **Compress:** process a batch, choose one of three image-quality levels, inspect before/after sizes for every file. Already optimized files are reported honestly. Text remains vector-based; images may lose detail. Output never grows just because of recompression.
- **Organize:** reorder, rotate, mark pages for removal, restore and undo. Preview changes before processing.
- **Remove pages:** explicit removal markers; at least one page must remain.
- **Rotate:** rotate individual, selected or all pages with updated previews.
- **Images to PDF:** order images, choose A4/Letter/Original, portrait/landscape and margins. Original follows the image dimensions at 150 DPI; orientation applies to A4/Letter. Update preview after editing margins.
- **Protect PDF:** set and confirm an 8–40 character password (maximum 40 UTF-8 bytes). The exported PDF uses AES-256 encryption and requires the password to open. Show/hide password is available; result continuation offers Unlock.
- **Unlock PDF:** enter the document password on import. A wrong password can be retried; cancelling preserves the previous task. Save a separate copy without encryption. Already unencrypted files are identified before replacing the task.
- **Watermark:** add a Unicode text watermark to all pages or a page range, with Top/Center/Bottom placement, font size and opacity. Update preview after changing settings before processing. Long text shrinks to fit; image watermarks are not included in this release.

- **PDF to JPG:** export all pages or a range in document order at 72, 150 or 300 DPI and 60%, 85% or 95% JPG quality. One page saves as JPG; multiple pages save as ZIP. Continue directly in Images to PDF. Very large pages require a lower DPI.
- **Page numbers:** select pages, starting number, top/bottom placement, font size and plain or Page n of total format. Numbering follows document order; the total is the last printed number. Update preview before processing.
- **Crop PDF:** choose pages and left/top/right/bottom margins as percentages of the displayed page. Update preview to see the resulting dimensions. Cropping hides content outside the crop box; it is not permanent redaction.

Passwords stay in memory for the current task and are cleared when that task is replaced or the app closes. They are not included in status JSON, result metadata or configuration files.

Input errors appear on individual cards so valid files remain accessible. Single-PDF tools use a single-file picker and reject multiple dropped inputs explicitly. Use Unlock PDF first for password-protected inputs.

Ctrl+O imports; Ctrl+Z undoes file/page changes. Home cards and controls support keyboard focus. There are no inactive conversion cards presented as working tools. Office conversion, OCR, signatures, cloud storage and AI features are not included.

## Build and verify

```powershell
python verify.py
python verify_ui.py
python verify_features.py
python verify_extended.py
python -m PyInstaller --noconfirm PDF-Studio.spec
& '.\.tools\inno\ISCC.exe' installer.iss
```

The spec includes TkDnD data for native file drops and locates Conda native DLLs when building outside an activated shell. `verify_ui.py` uses generated PDFs to check navigation, file recovery, split contracts, order/rotation, undo, batch compression, saving/retry, continuation, cancellation and preservation of original bytes. Run the built executable with `--smoke-test` to verify Tk/TkDnD startup and spawned Merge, Protect, Unlock, Watermark, JPG, Page numbers and Crop jobs inside the packaged app. `verify_installer.ps1` can test a temporary per-user installation only when PDF Studio is not already installed.

The source is separated into `pdf_workflow.py` (sessions and output validation), `jobs.py` (isolated processing), `pdf_tools.py` (PDF primitives) and `app.py` (desktop UI).

The executable is unsigned. See [the UX audit](docs/UX-AUDIT.md) and [the implementation notes](docs/UX-RELEASE.md).
