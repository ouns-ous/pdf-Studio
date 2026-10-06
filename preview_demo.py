from pathlib import Path
import pymupdf
from app import App

folder = Path('tmp')
folder.mkdir(exist_ok=True)
source = folder / 'preview-sample.pdf'
doc = pymupdf.open()
for i, title in enumerate(['Project overview', 'Our approach', 'Key milestones', 'Next steps']):
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(0, 0, 595, 18), color=None, fill=(.93, .19, .21))
    page.insert_text((50, 80), 'PDF STUDIO / SAMPLE', fontsize=11, color=(.45, .48, .54))
    page.insert_text((50, 135), title, fontsize=28, color=(.12, .16, .22))
    page.insert_text((50, 185), 'A simpler way to work with your documents.', fontsize=13)
    for y in range(240, 650, 30):
        page.draw_rect(pymupdf.Rect(50, y, 520 if y % 60 else 440, y + 8), color=None, fill=(.88, .90, .93))
    page.insert_text((50, 770), f'Page {i + 1}', fontsize=10)
doc.save(source)
doc.close()
app = App()
app.files = [str(source.resolve())]
app.refresh()
app.mainloop()
