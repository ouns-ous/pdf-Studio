from pathlib import Path
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageOps
import zipfile
import tempfile
import os


def selection(text, count):
    if not text.strip():
        return list(range(count))
    result = []
    for part in text.split(','):
        bounds = part.strip().split('-')
        if len(bounds) > 2:
            raise ValueError('Use page numbers like 1,3-5.')
        first = int(bounds[0])
        last = int(bounds[-1])
        if first < 1 or last < first or last > count:
            raise ValueError(f'Pages must be between 1 and {count}.')
        for number in range(first - 1, last):
            if number not in result:
                result.append(number)
    return result


def process(mode, files, output, pages='', angle=90, compression='Recommended compression'):
    output = Path(output)
    if any(Path(f).resolve() == output.resolve() for f in files):
        raise ValueError('Choose a different output filename to preserve your original.')
    if mode == 'Compress PDF':
        import pymupdf
        settings = {'Extreme compression': (100, 35), 'Recommended compression': (150, 65), 'Less compression': (220, 85)}
        dpi, quality = settings.get(compression, (150, 65))
        handle, temporary = tempfile.mkstemp(dir=output.parent, suffix='.pdf')
        os.close(handle)
        try:
            with pymupdf.open(files[0]) as doc:
                if doc.needs_pass:
                    raise ValueError('This PDF needs a password. Use an unprotected copy.')
                count = len(doc)
                doc.rewrite_images(dpi_threshold=dpi + 20, dpi_target=dpi, quality=quality, bitonal=False)
                doc.save(temporary, garbage=4, deflate=True)
            # Keep the original bytes when recompression would make the file larger.
            if Path(temporary).stat().st_size >= Path(files[0]).stat().st_size:
                Path(temporary).write_bytes(Path(files[0]).read_bytes())
            os.replace(temporary, output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return count
    writer = PdfWriter()
    if mode == 'Images to PDF':
        for filename in files:
            with Image.open(filename) as source:
                img = ImageOps.exif_transpose(source).convert('RGB')
                data = BytesIO()
                img.save(data, format='PDF', resolution=150)
                data.seek(0)
                writer.append(PdfReader(data))
    elif mode == 'Merge PDF':
        for filename in files:
            writer.append(filename)
    else:
        reader = PdfReader(files[0])
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('This PDF needs a password. Use an unprotected copy.')
        chosen = selection(pages, len(reader.pages))
        if mode == 'Delete pages' and not pages.strip():
            raise ValueError('Enter the page numbers to delete.')
        if mode == 'Delete pages':
            chosen = [i for i in range(len(reader.pages)) if i not in chosen]
        if mode in ('Rotate pages', 'Compress PDF'):
            chosen = list(range(len(reader.pages)))
        for index in chosen:
            page = reader.pages[index]
            if mode == 'Rotate pages' and index in selection(pages, len(reader.pages)):
                page.rotate(angle)
            writer.add_page(page)
        if mode == 'Compress PDF':
            for page in writer.pages:
                page.compress_content_streams()
    if not writer.pages:
        raise ValueError('The output must contain at least one page.')
    handle, temporary = tempfile.mkstemp(dir=output.parent, suffix='.pdf')
    os.close(handle)
    try:
        writer.write(temporary)
        writer.close()
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(PdfReader(output).pages)


def split_ranges(source, output, ranges, combine=False):
    count = len(PdfReader(source).pages)
    groups = [selection(f'{start}-{end}', count) for start, end in ranges]
    if not groups:
        raise ValueError('Add at least one range.')
    if combine:
        return process('Extract pages', [source], output,
                       ','.join(str(i + 1) for group in groups for i in group))
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError('Choose a different output filename.')
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'result.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for index, (start, end) in enumerate(ranges, 1):
                item = Path(directory) / f'range-{index}_{start}-{end}.pdf'
                process('Extract pages', [source], item, f'{start}-{end}')
                bundle.write(item, item.name)
        handle, temporary = tempfile.mkstemp(dir=Path(output).parent, suffix='.zip')
        os.close(handle)
        try:
            Path(temporary).write_bytes(archive.read_bytes())
            os.replace(temporary, output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return len(groups)
