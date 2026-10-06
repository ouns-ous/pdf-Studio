# PDF Studio 1.3

A local Windows PDF app with seven working tools: Merge, Split, Compress, Organize, Remove pages, Rotate, and Images to PDF.

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

Input errors appear on individual cards so valid files remain accessible. Single-PDF tools use a single-file picker and reject multiple dropped inputs explicitly. Password-protected PDFs require an unlocked copy.

Ctrl+O imports; Ctrl+Z undoes file/page changes. Home cards and controls support keyboard focus. There are no inactive conversion cards presented as working tools. Office conversion, OCR, signatures, cloud storage and AI features are not included.

## Build and verify

```powershell
python verify.py
python verify_ui.py
python -m PyInstaller --noconfirm PDF-Studio.spec
& '.\.tools\inno\ISCC.exe' installer.iss
```

The spec includes TkDnD data for native file drops. `verify_ui.py` uses generated PDFs to check navigation, file recovery, split contracts, order/rotation, undo, batch compression, saving/retry, continuation, cancellation and preservation of original bytes. Run the built executable with `--smoke-test` to verify Tk/TkDnD startup and a spawned PDF merge inside the packaged app. `verify_installer.ps1` can test a temporary per-user installation only when PDF Studio is not already installed.

The source is separated into `pdf_workflow.py` (sessions and output validation), `jobs.py` (isolated processing), `pdf_tools.py` (PDF primitives) and `app.py` (desktop UI).

The executable is unsigned. See [the UX audit](docs/UX-AUDIT.md) and [the implementation notes](docs/UX-RELEASE.md).
