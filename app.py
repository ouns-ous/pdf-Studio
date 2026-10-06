import os
import sys
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageOps, ImageTk
import pymupdf
from pdf_tools import process, split_ranges

BG, WHITE, INK, MUTED, RED = '#f5f5fa', '#ffffff', '#33333b', '#7a7a86', '#ee2e2e'
TOOLS = {
    'Merge PDF': 'Combine your PDFs in the order you choose.',
    'Split PDF': 'Choose ranges or click the pages you want to extract.',
    'Compress PDF': 'Reduce file size with lossless compression.',
    'Delete pages': 'Click the pages you want to remove.',
    'Rotate pages': 'Select pages, then choose a rotation.',
    'Images to PDF': 'Combine your images into one PDF.',
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PDF Studio')
        self.geometry('1360x768')
        self.minsize(1060, 680)
        self.configure(bg=BG)
        self.files, self.selected, self.images = [], set(), []
        self.cards, self.ranges = {}, []
        self.mode = 'Split PDF'
        self.busy = False
        self.total = self.offset = self.generation = 0
        self.events = queue.Queue()
        self.preview_pool = ThreadPoolExecutor(max_workers=1)
        self.split_mode = tk.StringVar(value='Ranges')
        self.combine = tk.BooleanVar(value=False)
        self.angle = tk.StringVar(value='90')
        self.compression = tk.StringVar(value='Recommended compression')
        self.home_active = False
        self.category = 'All'
        self.status = tk.StringVar(value='Ready. Your files stay on this computer.')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TProgressbar', background=RED, troughcolor=BG)
        header = tk.Frame(self, bg=WHITE)
        header.pack(fill='x')
        logo = self.button(header, 'I ♥ PDF', self.show_home)
        logo.config(font=('Georgia', 25, 'bold'))
        logo.pack(side='left', padx=(12, 20), pady=4)
        self.nav = {}
        for tool in ['Merge PDF', 'Split PDF', 'Compress PDF']:
            button = self.button(header, tool.upper(), lambda t=tool: self.change(t), small=True)
            button.pack(side='left', padx=12)
            self.nav[tool] = button
        self.button(header, 'CONVERT PDF  ▾', lambda: self.show_home('Convert PDF'), small=True).pack(side='left', padx=12)
        self.button(header, 'ALL PDF TOOLS  ▾', self.show_home, small=True).pack(side='left', padx=12)
        self.button(header, 'HOME  ▦', self.show_home, small=True).pack(side='right', padx=20)
        footer = tk.Frame(self, bg=WHITE)
        footer.pack(side='bottom', fill='x')
        self.label(footer, 'LOCAL & PRIVATE', 9, True, color=MUTED).pack(side='right', padx=20, pady=12)
        tk.Label(footer, textvariable=self.status, bg=WHITE, fg=MUTED, font=('Segoe UI', 10), anchor='w').pack(side='left', padx=20, pady=12)
        body = self.body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True)
        self.sidebar = tk.Frame(body, bg=WHITE, width=330)
        self.sidebar.pack(side='right', fill='y')
        self.sidebar.pack_propagate(False)
        workspace = self.workspace = tk.Frame(body, bg=BG)
        workspace.pack(side='left', fill='both', expand=True)
        toolbar = tk.Frame(workspace, bg=BG)
        toolbar.pack(fill='x', padx=24, pady=(22, 12))
        self.file_info = self.label(toolbar, 'No file selected', 11, color=MUTED, bg=BG)
        self.file_info.pack(side='left')
        self.button(toolbar, '+ Add files', self.add).pack(side='right')
        self.pager = tk.Frame(workspace, bg=BG)
        self.pager.pack(side='bottom', fill='x', padx=24, pady=8)
        self.canvas = tk.Canvas(workspace, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(workspace, orient='vertical', command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.gallery = tk.Frame(self.canvas, bg=BG)
        self.window = self.canvas.create_window((0, 0), window=self.gallery, anchor='nw')
        self.gallery.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind_all('<MouseWheel>', self.wheel)
        self.render_sidebar()
        self.refresh()
        self.show_home()
        self.after(80, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def show_home(self, category='All'):
        if self.busy:
            return
        self.home_active = True
        for button in self.nav.values():
            button.config(fg=INK)
        self.category = category
        self.sidebar.pack_forget()
        self.workspace.pack_forget()
        if hasattr(self, 'home'):
            self.home.destroy()
        self.home = tk.Frame(self.body, bg=BG)
        self.home.pack(fill='both', expand=True)
        self.label(self.home, 'Every tool you need to work with PDFs in one place', 30, True, bg=BG).pack(pady=(28, 4))
        self.label(self.home, 'Merge, split, compress, convert and organize your PDFs with just a few clicks.', 17, bg=BG).pack(pady=(0, 26))
        filters = tk.Frame(self.home, bg=BG)
        filters.pack(fill='x', padx=30, pady=(0, 20))
        categories = ['All', 'Workflows', 'Organize PDF', 'Optimize PDF', 'Convert PDF', 'Edit PDF', 'PDF Security', 'PDF Intelligence']
        for name in categories:
            button = self.button(filters, name, lambda c=name: self.show_home(c), small=True)
            button.config(bg='#292930' if name == category else WHITE, fg=WHITE if name == category else INK, padx=16, pady=8)
            button.pack(side='left', padx=6)
        canvas = tk.Canvas(self.home, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.home, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True, padx=28)
        canvas.configure(yscrollcommand=scroll.set)
        grid = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=grid, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        grid.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-int(e.delta / 120), 'units'))
        catalog = [
            ('Merge PDF', 'Organize PDF', '↘↖', '#f5684b', TOOLS['Merge PDF'], 'Merge PDF'),
            ('Split PDF', 'Organize PDF', '↖↘', '#f5684b', TOOLS['Split PDF'], 'Split PDF'),
            ('Compress PDF', 'Optimize PDF', '⇲', '#8cba59', 'Reduce file size while optimizing for maximal PDF quality.', 'Compress PDF'),
            ('PDF to Word', 'Convert PDF', 'W', '#5b80c7', 'Convert PDF files into editable Word documents.', None),
            ('PDF to PowerPoint', 'Convert PDF', 'P', '#ff7450', 'Turn your PDF files into editable presentations.', None),
            ('PDF to Excel', 'Convert PDF', 'X', '#60a468', 'Extract PDF data into Excel spreadsheets.', None),
            ('Word to PDF', 'Convert PDF', 'W ↘', '#5b80c7', 'Convert Word documents to PDF.', None),
            ('PowerPoint to PDF', 'Convert PDF', 'P ↘', '#ff7450', 'Convert presentations to PDF.', None),
            ('Excel to PDF', 'Convert PDF', 'X ↘', '#60a468', 'Convert spreadsheets to PDF.', None),
            ('PDF to JPG', 'Convert PDF', 'JPG', '#d4c52c', 'Export PDF pages as images.', None),
            ('JPG to PDF', 'Convert PDF', '▧', '#d4c52c', TOOLS['Images to PDF'], 'Images to PDF'),
            ('Organize PDF', 'Organize PDF', 'A B', '#f5684b', 'Select and remove pages from your PDF.', 'Delete pages'),
            ('Scan to PDF', 'Organize PDF', '▤', '#f5684b', 'Capture document scans and create a PDF.', None),
            ('Repair PDF', 'Optimize PDF', '⚒', '#8cba59', 'Repair damaged PDF documents.', None),
            ('OCR PDF', 'Optimize PDF', 'OCR', '#8cba59', 'Make scanned PDF documents searchable.', None),
            ('Edit PDF', 'Edit PDF', 'T', '#ab6796', 'Add text, images and annotations to a PDF.', None),
            ('Watermark', 'Edit PDF', '▣', '#ab6796', 'Stamp an image or text over your PDF.', None),
            ('Rotate PDF', 'Edit PDF', '↻', '#ab6796', TOOLS['Rotate pages'], 'Rotate pages'),
            ('Page numbers', 'Edit PDF', '1 2', '#ab6796', 'Add page numbers to PDF documents.', None),
            ('Crop PDF', 'Edit PDF', '⌗', '#ab6796', 'Crop the margins of your PDF pages.', None),
            ('PDF Forms', 'Edit PDF', 'Ab', '#ab6796', 'Fill in PDF form fields.', None),
            ('Sign PDF', 'PDF Security', '✒', '#4d7daf', 'Sign PDF documents electronically.', None),
            ('Unlock PDF', 'PDF Security', '♙', '#4d7daf', 'Remove PDF password protection.', None),
            ('Protect PDF', 'PDF Security', '♜', '#4d7daf', 'Encrypt your PDF with a password.', None),
            ('Compare PDF', 'PDF Security', '▥', '#4d7daf', 'Compare two document versions.', None),
            ('Redact PDF', 'PDF Security', '▤', '#4d7daf', 'Remove sensitive content from documents.', None),
            ('Summarize PDF', 'PDF Intelligence', '✦', '#7f72bb', 'Create a summary of a PDF document.', None),
            ('Create a workflow', 'Workflows', '+', '#f5684b', 'Combine your favorite tools into a reusable workflow.', None),
        ]
        shown = [item for item in catalog if category == 'All' or item[1] == category]
        for index, (title, group, icon, color, description, mode) in enumerate(shown):
            card = tk.Frame(grid, bg=WHITE, highlightthickness=1, highlightbackground='#d5d5e1', padx=24, pady=22, width=285, height=245)
            card.grid(row=index // 4, column=index % 4, sticky='nsew', padx=9, pady=9)
            card.grid_propagate(False)
            badge = self.label(card, icon, 20, True, color=WHITE, bg=color)
            badge.place(x=0, y=0, width=48, height=48)
            heading = self.label(card, title, 16, True)
            heading.place(x=0, y=68)
            detail = self.label(card, description, 11, color=MUTED)
            detail.config(wraplength=240)
            detail.place(x=0, y=108)
            if mode is None:
                self.label(card, 'Coming soon', 9, color=MUTED).place(x=0, y=185)
            def activate(event=None, target=mode, name=title):
                if target:
                    self.change(target)
                else:
                    self.status.set(name + ' is not available in this desktop version yet.')
            for widget in [card, badge, heading, detail]:
                widget.configure(cursor='hand2')
                widget.bind('<Button-1>', activate)
                widget.bind('<Enter>', lambda e, c=card: c.configure(highlightbackground='#33333b'))
                widget.bind('<Leave>', lambda e, c=card: c.configure(highlightbackground='#d5d5e1'))
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1, uniform='cards')
        self.status.set('Your files stay on this computer. Choose a PDF tool to get started.')

    def label(self, parent, text, size=11, bold=False, color=INK, bg=WHITE):
        return tk.Label(parent, text=text, font=('Segoe UI', size, 'bold' if bold else 'normal'), bg=bg, fg=color, justify='left')

    def button(self, parent, text, command, accent=False, small=False):
        return tk.Button(parent, text=text, command=command, font=('Segoe UI', 10 if small else 11, 'bold'), bg=RED if accent else WHITE, fg=WHITE if accent else INK, activebackground='#d7232b' if accent else '#eeeef4', activeforeground=WHITE if accent else INK, relief='flat', bd=0, cursor='hand2', padx=12, pady=10 if small else 12)

    def wheel(self, event):
        if self.canvas.winfo_rootx() <= event.x_root <= self.canvas.winfo_rootx() + self.canvas.winfo_width():
            self.canvas.yview_scroll(-int(event.delta / 120), 'units')

    def close(self):
        if self.busy:
            self.status.set('Please wait for processing to finish before closing.')
        else:
            self.destroy()

    def destroy(self):
        self.preview_pool.shutdown(wait=False, cancel_futures=True)
        super().destroy()

    def change(self, mode):
        if self.busy:
            return
        self.home_active = False
        if hasattr(self, 'home'):
            self.home.destroy()
        self.workspace.pack(side='left', fill='both', expand=True)
        if self.busy:
            return
        if (mode == 'Images to PDF') != (self.mode == 'Images to PDF'):
            self.files.clear()
        elif mode not in ('Merge PDF', 'Images to PDF'):
            self.files = self.files[:1]
        self.mode = mode
        self.selected.clear()
        self.ranges.clear()
        self.offset = 0
        self.render_sidebar()
        self.refresh()

    def render_sidebar(self):
        for child in self.sidebar.winfo_children():
            child.destroy()
        for name, button in self.nav.items():
            button.config(fg=RED if name == self.mode else INK)
        self.label(self.sidebar, 'Compression level' if self.mode == 'Compress PDF' else ('Split' if self.mode == 'Split PDF' else self.mode), 24, True).pack(pady=(14, 8))
        text = self.label(self.sidebar, TOOLS[self.mode], color=MUTED)
        text.config(wraplength=280)
        text.pack(padx=22, pady=(0, 18))
        bottom = tk.Frame(self.sidebar, bg=WHITE)
        bottom.pack(side='bottom', fill='x', padx=22, pady=22)
        self.progress = ttk.Progressbar(bottom, mode='indeterminate')
        self.progress.pack(fill='x', pady=8)
        self.action = self.button(bottom, self.mode + '  →', self.run, accent=True)
        self.action.config(font=('Segoe UI', 16, 'bold'), pady=18)
        self.action.pack(fill='x')
        self.options = tk.Frame(self.sidebar, bg=WHITE)
        self.options.pack(fill='both', expand=True, padx=22)
        if self.mode == 'Split PDF':
            tabs = tk.Frame(self.options, bg=WHITE)
            tabs.pack(fill='x', pady=(0, 18))
            for name in ['Ranges', 'Pages']:
                tk.Radiobutton(tabs, text=name, variable=self.split_mode, value=name, indicatoron=False, command=self.switch_split, bg=WHITE, selectcolor='#ffeded', fg=INK, font=('Segoe UI', 11), padx=18, pady=12, relief='groove', bd=1).pack(side='left', expand=True, fill='x')
            if self.split_mode.get() == 'Ranges':
                self.label(self.options, 'Range mode: Custom', 12, True).pack(anchor='w', pady=(0, 10))
                canvas = tk.Canvas(self.options, bg=WHITE, height=80, highlightthickness=0)
                self.range_box = tk.Frame(canvas, bg=WHITE)
                canvas.create_window((0, 0), window=self.range_box, anchor='nw', width=278)
                self.range_box.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
                canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-int(e.delta / 120), 'units'))
                for a, b in self.ranges:
                    self.range_row(a, b)
                self.label(self.options, 'Separate ranges are saved in a ZIP.', 9, color=MUTED).pack(side='bottom', anchor='w')
                tk.Checkbutton(self.options, text='Merge ranges into one PDF', variable=self.combine, bg=WHITE, font=('Segoe UI', 10), activebackground=WHITE).pack(side='bottom', anchor='w', pady=8)
                self.button(self.options, '+ Add range', self.add_range).pack(side='bottom', fill='x', pady=8)
                canvas.pack(fill='both', expand=True)
            else:
                self.selection_options()
        elif self.mode in ('Delete pages', 'Rotate pages'):
            self.selection_options()
            if self.mode == 'Rotate pages':
                self.label(self.options, 'Rotate clockwise', 12, True).pack(anchor='w', pady=(20, 10))
                ttk.Combobox(self.options, textvariable=self.angle, values=['90', '180', '270'], state='readonly', width=12).pack(anchor='w')
        elif self.mode == 'Compress PDF':
            for title, description in [('Extreme compression', 'Less quality, high compression'), ('Recommended compression', 'Good quality, good compression'), ('Less compression', 'High quality, less compression')]:
                row = tk.Frame(self.options, bg=WHITE, pady=14)
                row.pack(fill='x')
                tk.Radiobutton(row, text=title.upper(), variable=self.compression, value=title, bg=WHITE, fg=RED, activebackground=WHITE, font=('Segoe UI', 11), anchor='w').pack(fill='x')
                self.label(row, description, 11).pack(anchor='w', padx=22)
            self.label(self.options, 'Image quality can change. Text stays sharp.', 9, color=MUTED).pack(anchor='w', pady=12)
        else:
            note = self.label(self.options, 'Use the arrows below each file to change the output order.', color=MUTED)
            note.config(wraplength=280)
            note.pack(anchor='w', pady=10)
        self.update_action()

    def switch_split(self):
        if not self.busy:
            self.render_sidebar()
            self.paint_selection()

    def selection_options(self):
        self.selected_label = self.label(self.options, f'{len(self.selected)} pages selected', 12, True)
        self.selected_label.pack(anchor='w', pady=10)
        self.button(self.options, 'Select all pages', self.select_all).pack(fill='x', pady=4)
        self.button(self.options, 'Clear selection', self.clear_selection).pack(fill='x', pady=4)

    def range_row(self, a, b):
        row = tk.Frame(self.range_box, bg=BG, padx=8, pady=8)
        row.pack(fill='x', pady=4)
        self.label(row, 'From', 10, bg=BG).pack(side='left')
        tk.Spinbox(row, from_=1, to=max(1, self.total), textvariable=a, width=4, font=('Segoe UI', 12), relief='solid', bd=1).pack(side='left', padx=6)
        self.label(row, 'to', 10, bg=BG).pack(side='left')
        tk.Spinbox(row, from_=1, to=max(1, self.total), textvariable=b, width=4, font=('Segoe UI', 12), relief='solid', bd=1).pack(side='left', padx=6)
        self.button(row, '×', lambda: self.remove_range(a), small=True).pack(side='right')

    def add_range(self):
        if self.busy or not self.files or not self.total:
            return
        self.ranges.append(self.new_range(1, self.total))
        self.render_sidebar()

    def new_range(self, start, end):
        pair = (tk.StringVar(value=str(start)), tk.StringVar(value=str(end)))
        for variable in pair:
            variable.trace_add('write', lambda *args: self.paint_selection())
        return pair

    def remove_range(self, a):
        if not self.busy:
            self.ranges = [pair for pair in self.ranges if pair[0] is not a]
            self.render_sidebar()

    def add(self):
        if self.busy:
            return
        types = [('Images', '*.jpg *.jpeg *.png *.bmp *.tif *.tiff')] if self.mode == 'Images to PDF' else [('PDF files', '*.pdf')]
        files = filedialog.askopenfilenames(title='Choose your files', filetypes=types)
        if not files:
            return
        if self.mode in ('Merge PDF', 'Images to PDF'):
            self.files.extend(files)
        else:
            self.files = [files[0]]
        self.selected.clear()
        self.ranges.clear()
        self.offset = 0
        self.refresh()

    def refresh(self):
        self.generation += 1
        generation = self.generation
        self.cards.clear()
        self.images.clear()
        for child in self.gallery.winfo_children():
            child.destroy()
        for child in self.pager.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)
        self.total = 0
        if self.home_active:
            self.home.destroy()
            self.home_active = False
            self.workspace.pack(side='left', fill='both', expand=True)
        if not self.files:
            self.sidebar.pack_forget()
            empty = tk.Frame(self.gallery, bg=BG)
            empty.pack(pady=30)
            self.label(empty, 'Merge PDF files' if self.mode == 'Merge PDF' else self.mode, 34, True, bg=BG).pack(pady=12)
            self.label(empty, TOOLS[self.mode], 18, color=INK, bg=BG).pack(pady=8)
            select = self.button(empty, 'Select images' if self.mode == 'Images to PDF' else 'Select PDF files', self.add, accent=True)
            select.config(font=('Segoe UI', 20, 'bold'), padx=70, pady=22)
            select.pack(pady=24)
            self.file_info.config(text='No file selected')
            self.render_sidebar()
            return
        self.sidebar.pack(side='right', fill='y', before=self.workspace)
        self.status.set('Loading previews…')
        self.action.config(state='disabled')
        files, mode, offset = list(self.files), self.mode, self.offset
        def load():
            try:
                previews = []
                if mode in ('Merge PDF', 'Images to PDF'):
                    total = len(files)
                    for index in range(offset, min(offset + 12, total)):
                        file = files[index]
                        if mode == 'Images to PDF':
                            with Image.open(file) as source:
                                image = ImageOps.exif_transpose(source).convert('RGB')
                                image.thumbnail((150, 195))
                                image = image.copy()
                            detail = Path(file).name
                        else:
                            with pymupdf.open(file) as doc:
                                if doc.needs_pass:
                                    raise ValueError('This PDF is password protected. Choose an unprotected copy.')
                                image = self.thumbnail(doc[0])
                                detail = f'{Path(file).name}\n{len(doc)} pages'
                        previews.append((index, image, detail))
                else:
                    with pymupdf.open(files[0]) as doc:
                        if doc.needs_pass:
                            raise ValueError('This PDF is password protected. Choose an unprotected copy.')
                        total = len(doc)
                        for index in range(offset, min(offset + 12, total)):
                            previews.append((index, self.thumbnail(doc[index]), f'Page {index + 1}'))
                self.events.put(('preview', generation, total, previews))
            except Exception as error:
                self.events.put(('preview_error', generation, str(error)))
        self.preview_pool.submit(load)

    @staticmethod
    def thumbnail(page):
        scale = min(150 / page.rect.width, 195 / page.rect.height)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
        return Image.open(BytesIO(pix.tobytes('png'))).copy()

    def show_previews(self, total, previews):
        self.total = total
        multi = self.mode in ('Merge PDF', 'Images to PDF')
        self.file_info.config(text=f'{total} files' if multi else f'{Path(self.files[0]).name[:48]}  ·  {total} pages')
        for position, (index, image, detail) in enumerate(previews):
            frame = tk.Frame(self.gallery, bg=WHITE, highlightthickness=2, highlightbackground='#e2e3eb', padx=10, pady=10)
            frame.grid(row=position // 3, column=position % 3, padx=12, pady=12, sticky='n')
            photo = ImageTk.PhotoImage(image)
            self.images.append(photo)
            preview = tk.Label(frame, image=photo, bg=WHITE, width=160, height=200, cursor='hand2')
            preview.pack()
            label = self.label(frame, detail if len(detail) < 42 else detail[:38] + '…', 10)
            label.pack(pady=(8, 2))
            self.cards[index] = frame
            if multi:
                controls = tk.Frame(frame, bg=WHITE)
                controls.pack()
                for text, command in [('←', lambda i=index: self.move(i, -1)), ('→', lambda i=index: self.move(i, 1)), ('×', lambda i=index: self.remove(i))]:
                    self.button(controls, text, command, small=True).pack(side='left')
            else:
                for widget in [frame, preview, label]:
                    widget.bind('<Button-1>', lambda e, i=index: self.toggle(i))
        for column in range(3):
            self.gallery.grid_columnconfigure(column, weight=1)
        if self.offset:
            self.button(self.pager, '← Previous', lambda: self.paginate(-12)).pack(side='left')
        self.label(self.pager, f'{self.offset + 1}–{min(self.offset + 12, total)} of {total}', 10, color=MUTED, bg=BG).pack(side='left', padx=16)
        if self.offset + 12 < total:
            self.button(self.pager, 'Next →', lambda: self.paginate(12)).pack(side='right')
        if not self.ranges and not multi:
            self.ranges = [self.new_range(1, total)]
        self.render_sidebar()
        self.paint_selection()
        self.status.set('Click page previews to select them.' if not multi else 'Use the arrows to arrange your files.')

    def paginate(self, delta):
        if not self.busy:
            self.offset = max(0, self.offset + delta)
            self.refresh()

    def toggle(self, index):
        if self.busy or self.mode not in ('Split PDF', 'Delete pages', 'Rotate pages'):
            return
        if self.mode == 'Split PDF' and self.split_mode.get() != 'Pages':
            self.split_mode.set('Pages')
            self.render_sidebar()
        if index in self.selected:
            self.selected.remove(index)
        else:
            self.selected.add(index)
        self.paint_selection()

    def paint_selection(self):
        marked = self.selected
        if self.mode == 'Split PDF' and self.split_mode.get() == 'Ranges':
            marked = set()
            for a, b in self.ranges:
                try:
                    start, end = int(a.get()), int(b.get())
                    if 1 <= start <= end <= self.total:
                        marked.update(range(start - 1, end))
                except ValueError:
                    pass
        for index, card in self.cards.items():
            card.config(highlightbackground=RED if index in marked else '#e2e3eb')
        if hasattr(self, 'selected_label') and self.selected_label.winfo_exists():
            self.selected_label.config(text=f'{len(self.selected)} pages selected')
        self.update_action()

    def select_all(self):
        if not self.busy:
            self.selected = set(range(self.total))
            self.paint_selection()

    def clear_selection(self):
        if not self.busy:
            self.selected.clear()
            self.paint_selection()

    def update_action(self):
        enabled = bool(self.files and self.total and not self.busy)
        if self.mode == 'Merge PDF':
            enabled = enabled and len(self.files) > 1
        if self.mode in ('Delete pages', 'Rotate pages') or (self.mode == 'Split PDF' and self.split_mode.get() == 'Pages'):
            enabled = enabled and bool(self.selected)
        if self.mode == 'Delete pages' and len(self.selected) == self.total:
            enabled = False
        if self.mode == 'Split PDF' and self.split_mode.get() == 'Ranges':
            enabled = enabled and bool(self.ranges)
        self.action.config(state='normal' if enabled else 'disabled')

    def move(self, index, delta):
        if not self.busy and 0 <= index + delta < len(self.files):
            self.files[index], self.files[index + delta] = self.files[index + delta], self.files[index]
            self.refresh()

    def remove(self, index):
        if not self.busy:
            del self.files[index]
            if self.offset >= len(self.files):
                self.offset = max(0, self.offset - 12)
            self.refresh()

    def run(self):
        if self.busy or not self.files or not self.total:
            return
        ranges = None
        if self.mode == 'Split PDF' and self.split_mode.get() == 'Ranges':
            try:
                ranges = [(int(a.get()), int(b.get())) for a, b in self.ranges]
                if not ranges or any(a < 1 or b < a or b > self.total for a, b in ranges):
                    raise ValueError()
            except ValueError:
                self.status.set(f'Enter valid ranges between page 1 and {self.total}.')
                return
        archive = ranges is not None and not self.combine.get()
        extension = '.zip' if archive else '.pdf'
        output = filedialog.asksaveasfilename(title='Save your result', defaultextension=extension, initialfile=self.mode.lower().replace(' ', '-') + extension, filetypes=[('ZIP archive' if archive else 'PDF file', '*' + extension)])
        if not output:
            return
        mode, files, angle, combine = self.mode, list(self.files), int(self.angle.get()), self.combine.get()
        compression = self.compression.get()
        pages = ','.join(str(i + 1) for i in sorted(self.selected))
        self.busy = True
        self.action.config(state='disabled', text='Processing…')
        self.progress.start(12)
        self.status.set('Creating your result…')
        def worker():
            try:
                count = split_ranges(files[0], output, ranges, combine) if ranges is not None else process('Extract pages' if mode == 'Split PDF' else mode, files, output, pages, angle, compression)
                self.events.put(('done', output, count, archive, None))
            except Exception as error:
                self.events.put(('done', output, 0, archive, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'preview' and event[1] == self.generation:
                    self.show_previews(event[2], event[3])
                elif event[0] == 'preview_error' and event[1] == self.generation:
                    self.status.set(event[2])
                    self.total = 0
                    self.update_action()
                elif event[0] == 'done':
                    self.done(*event[1:])
        except queue.Empty:
            pass
        self.after(80, self.poll)

    def done(self, output, count, archive, error):
        self.busy = False
        self.progress.stop()
        self.action.config(text=self.mode + '  →')
        self.update_action()
        if error:
            self.status.set('Could not save: ' + error)
            return
        self.status.set(f'Saved successfully: {Path(output).name}')
        dialog = tk.Toplevel(self)
        dialog.title('Your result is ready')
        dialog.geometry('440x260')
        dialog.resizable(False, False)
        dialog.configure(bg=WHITE)
        dialog.transient(self)
        self.label(dialog, 'Done! Your file is ready.', 20, True).pack(pady=(30, 12))
        self.label(dialog, f'{count} ' + ('PDF files in ZIP' if archive else 'pages saved'), color=MUTED).pack()
        self.button(dialog, 'Open result', lambda: os.startfile(output), accent=True).pack(pady=14)
        self.button(dialog, 'Show in folder', lambda: os.startfile(str(Path(output).parent))).pack()


if __name__ == '__main__':
    app = App()
    if '--smoke-test' in sys.argv:
        app.withdraw()
        app.update()
        app.destroy()
    else:
        app.mainloop()
