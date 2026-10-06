# PDF Studio

Windows desktop PDF utilities with page thumbnails, a dedicated options panel, click-to-select pages, merge ordering, split ranges, deletion, rotation, three image compression levels, and images to PDF. All processing is local.

Run `dist/PDF-Studio-Setup.exe` to install PDF Studio for the current Windows user. Setup adds a Start Menu shortcut, offers an optional desktop shortcut, and registers an uninstaller in Windows Installed apps. The default install folder is `%LOCALAPPDATA%\Programs\PDF Studio`. No Python installation or administrator access is required.

`dist/PDF-Studio.exe` is also available as a portable executable.

To develop: `python -m pip install -r requirements.txt`, then `python app.py`.

To build: `python -m PyInstaller --noconfirm --onefile --windowed --exclude-module numpy --exclude-module scipy --exclude-module matplotlib --exclude-module pandas --name PDF-Studio app.py`.

To package the installer with Inno Setup 6: `ISCC.exe installer.iss`.

Choose a tool in the top bar, select a file, configure the panel on the right, then press the red action button. The result dialog provides Open result and Show in folder.

Split supports editable start/end ranges or individual pages selected from thumbnails. Separate ranges export as PDFs in one ZIP; the merge checkbox exports one PDF. Click previews to select pages for deletion or rotation. Select all and Clear selection are available. Page previews are loaded in batches of 12 with Previous/Next controls. PDF tools reuse the loaded PDF when switching; image conversion uses a separate file selection.

Compression offers Extreme, Recommended and Less compression, with different image resolution and JPEG quality settings. Text remains vector-based. When compression would increase file size, the original bytes are saved instead. Run `python verify.py` and `python verify_ui.py` for functional checks.

This is an initial independent application; it does not include Word conversion, OCR or electronic signatures. The executable is unsigned.

The app opens on a tool catalog with category filters, inspired by the supplied reference screenshots. Merge, Split, Compress, Organize (delete pages), Rotate and JPG/images to PDF work locally. Other catalog entries are explicitly marked Coming soon. No account or cloud login is required.
