import json, sys, time, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf
from app import App
from pdf_tools import split_ranges

def ready(app):
    end=time.monotonic()+15
    while app.total == 0:
        app.update()
        if time.monotonic()>end:
            raise RuntimeError(app.status.get())
        time.sleep(.01)
    app.update()

findings={}
with tempfile.TemporaryDirectory() as directory:
    paths=[]
    for name in ['A','B']:
        path=Path(directory)/(name+'.pdf')
        with pymupdf.open() as doc:
            for i in range(3):
                page=doc.new_page(); page.insert_text((50,60),f'{name} page {i+1}')
            doc.save(path)
        paths.append(str(path))
    app=App(); app.withdraw()
    app.change('Merge PDF'); app.files=paths.copy(); app.refresh(); ready(app)
    app.change('Compress PDF'); ready(app)
    app.change('Merge PDF'); ready(app)
    findings['navigation_loses_merge_files']={'before':2,'after':len(app.files)}
    app.change('Split PDF'); ready(app)
    app.ranges[0][0].set('3'); app.ranges[0][1].set('1')
    findings['invalid_range_action_enabled']={'range':'3-1','action':str(app.action['state'])}
    app.ranges[0][0].set('1'); app.ranges[0][1].set('2')
    app.toggle(0)
    findings['preview_click_changes_split_mode']={'before':'Ranges','after':app.split_mode.get()}
    app.change('Compress PDF'); ready(app)
    with patch('app.filedialog.askopenfilenames',return_value=tuple(paths)):
        app.add()
    ready(app)
    findings['multiple_compression_inputs_ignored']={'chosen':2,'retained':len(app.files)}
    app.change('Split PDF'); ready(app)
    app.ranges[0][0].set('2'); app.ranges[0][1].set('2')
    app.change('Split PDF'); ready(app)
    findings['same_tool_resets_range']={'before':['2','2'],'after':[v.get() for v in app.ranges[0]]}
    output=Path(directory)/'overlap.pdf'
    split_ranges(paths[0],output,[(1,2),(2,3)],True)
    with pymupdf.open(output) as doc:
        findings['overlapping_ranges_deduplicated']={'requested_pages':[1,2,2,3],'actual_pages':len(doc)}
    bad=Path(directory)/'bad.pdf'; bad.write_text('not a PDF')
    app.change('Merge PDF'); app.files=[paths[0],str(bad)]; app.refresh()
    end=time.monotonic()+15
    while app.status.get()=='Loading previews…' and time.monotonic()<end:
        app.update(); time.sleep(.01)
    findings['bad_merge_file_blocks_recovery']={'loaded_cards':len(app.cards),'files':len(app.files),'total':app.total,'error':'PDF cannot be opened' if 'Failed to open' in app.status.get() else app.status.get()}
    app.destroy()
print(json.dumps(findings,indent=2))
