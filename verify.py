from tempfile import TemporaryDirectory
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from PIL import Image
from pdf_tools import process, selection

with TemporaryDirectory() as folder:
    root = Path(folder)
    source = root / 'source.pdf'
    writer = PdfWriter()
    for width in [100, 200, 300]:
        writer.add_blank_page(width=width, height=400)
    writer.write(source)
    output = root / 'output.pdf'
    assert process('Merge PDF', [source, source], output) == 6
    assert process('Extract pages', [source], output, '3,1') == 2
    assert [float(p.mediabox.width) for p in PdfReader(output).pages] == [300, 100]
    assert process('Delete pages', [source], output, '2') == 2
    assert [float(p.mediabox.width) for p in PdfReader(output).pages] == [100, 300]
    assert process('Rotate pages', [source], output, '2', 90) == 3
    assert [p.rotation for p in PdfReader(output).pages] == [0, 90, 0]
    assert process('Compress PDF', [source], output) == 3
    image = root / 'image.png'
    Image.new('RGB', (120, 80), 'red').save(image)
    assert process('Images to PDF', [image, image], output) == 2
    for invalid in ['0', '4', '3-1']:
        try:
            selection(invalid, 3)
            raise AssertionError('Invalid selection accepted')
        except ValueError:
            pass
    before = source.read_bytes()
    try:
        process('Merge PDF', [source], source)
        raise AssertionError('Source overwrite accepted')
    except ValueError:
        pass
    assert source.read_bytes() == before
    try:
        process('Delete pages', [source], output, '1-3')
        raise AssertionError('Empty output accepted')
    except ValueError:
        pass
print('All six tools and validation checks passed.')
