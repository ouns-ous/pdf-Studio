import time
import tempfile
import zipfile
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
import pymupdf
from app import App
from pdf_tools import split_ranges


def pump(app, condition):
    deadline = time.monotonic() + 12
    while not condition():
        app.update()
        if time.monotonic() > deadline:
            raise AssertionError('Preview did not finish')
        time.sleep(.02)
    app.update()


with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'sample.pdf'
    doc = pymupdf.open()
    for i in range(15):
        page = doc.new_page()
        page.insert_text((60, 80), f'Sample page {i + 1}', fontsize=24)
    doc.save(source)
    doc.close()
    output = Path(directory) / 'split.zip'
    assert split_ranges(source, output, [(1, 2), (4, 5)]) == 2
    with zipfile.ZipFile(output) as bundle:
        assert len(bundle.namelist()) == 2
        for name in bundle.namelist():
            assert len(PdfReader(BytesIO(bundle.read(name))).pages) == 2
    combined = Path(directory) / 'combined.pdf'
    assert split_ranges(source, combined, [(1, 2), (4, 5)], True) == 4
    assert 'Sample page 4' in PdfReader(combined).pages[2].extract_text()
    before = output.read_bytes()
    try:
        split_ranges(source, output, [(1, 99)])
        raise AssertionError('Invalid range accepted')
    except ValueError:
        pass
    assert output.read_bytes() == before
    app = App()
    app.withdraw()
    assert app.home_active
    for category in ['Organize PDF', 'Optimize PDF', 'Convert PDF', 'Edit PDF', 'PDF Security', 'Workflows']:
        app.show_home(category)
        app.update_idletasks()
        assert app.category == category
    app.change('Split PDF')
    app.files = [str(source)]
    app.refresh()
    pump(app, lambda: app.total == 15)
    assert len(app.cards) == 12 and len(app.ranges) == 1
    for width, height in [(1200, 720), (1060, 680)]:
        app.geometry(f'{width}x{height}')
        app.update_idletasks()
        assert app.action.winfo_height() > 40
        assert app.action.winfo_rooty() + app.action.winfo_height() <= app.sidebar.winfo_rooty() + app.sidebar.winfo_height()
        assert app.nav['Compress PDF'].winfo_x() + app.nav['Compress PDF'].winfo_width() <= width
    app.ranges[0][0].set('2')
    app.ranges[0][1].set('3')
    assert app.cards[0]['highlightbackground'] != app.cards[1]['highlightbackground']
    app.toggle(0)
    assert app.split_mode.get() == 'Pages' and app.selected == {0}
    app.paginate(12)
    pump(app, lambda: app.total == 15)
    assert set(app.cards) == {12, 13, 14} and app.selected == {0}
    app.toggle(14)
    assert app.selected == {0, 14}
    app.change('Delete pages')
    pump(app, lambda: app.total == 15)
    assert app.files == [str(source)]
    app.select_all()
    assert str(app.action['state']) == 'disabled'
    app.clear_selection()
    app.toggle(1)
    assert str(app.action['state']) == 'normal'
    app.change('Rotate pages')
    pump(app, lambda: app.total == 15)
    app.select_all()
    assert len(app.selected) == 15
    app.destroy()
print('Range export, preservation, preview pagination and page selection passed.')
