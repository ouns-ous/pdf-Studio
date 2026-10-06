import json
import multiprocessing as mp
import os
import queue
import shutil
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from PIL import Image, ImageOps, ImageTk
import pymupdf
from tkinterdnd2 import TkinterDnD, DND_FILES
from pdf_workflow import Session, TOOLS, BATCH
from jobs import run_job, image_page_size
from pdf_tools import selection

BG, WHITE, INK, MUTED, RED = "#f5f5fa", "#ffffff", "#33333b", "#70717e", "#ee2e2e"


def size_text(value):
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024 / 1024:.2f} MB"


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Studio")
        self.geometry("1360x820")
        self.minsize(1060, 680)
        self.configure(bg=BG)
        self.sessions = {mode: Session(mode) for mode in TOOLS}
        self.mode = "Merge PDF"
        self.home_active = False
        self.busy = self.loading = False
        self.generation = 0
        self.images, self.cards, self.card_badges, self.preview_data = [], {}, {}, []
        self.events = queue.Queue()
        self.preview_pool = ThreadPoolExecutor(max_workers=2)
        self.temporary = tempfile.TemporaryDirectory(prefix="pdf-studio-")
        self.job = None
        self.poll_id = None
        self.syncing = False
        self.status = tk.StringVar(value="Your files stay on this computer.")
        self.validation = tk.StringVar()
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar", background=RED, troughcolor=BG)
        header = tk.Frame(self, bg=WHITE)
        header.pack(fill="x")
        logo = self.button(header, "PDF Studio", self.show_home)
        logo.config(font=("Segoe UI", 22, "bold"))
        logo.pack(side="left", padx=(20, 22), pady=10)
        self.nav = {}
        for mode in ["Merge PDF", "Split PDF", "Compress PDF"]:
            button = self.button(
                header, mode.upper(), lambda m=mode: self.change(m), small=True
            )
            button.pack(side="left", padx=5)
            self.nav[mode] = button
        for text, modes in [
            ("CONVERT PDF ▾", ["Images to PDF"]),
            ("ALL PDF TOOLS ▾", list(TOOLS)),
        ]:
            button = self.button(header, text, lambda: None, small=True)
            button.config(command=lambda b=button, ms=modes: self.tool_menu(b, ms))
            button.pack(side="left", padx=5)
        self.button(header, "Home", self.show_home, small=True).pack(
            side="right", padx=15
        )
        footer = tk.Frame(self, bg=WHITE)
        footer.pack(side="bottom", fill="x")
        self.label(footer, "LOCAL & PRIVATE", 9, color=MUTED).pack(
            side="right", padx=20, pady=10
        )
        tk.Label(
            footer,
            textvariable=self.status,
            anchor="w",
            bg=WHITE,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=20, pady=10, fill="x", expand=True)
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.bind_all("<MouseWheel>", self.wheel)
        self.bind_all("<FocusIn>", self.reveal_focus)
        self.bind("<Control-o>", lambda e: self.add() if not self.home_active else None)
        self.bind(
            "<Control-z>",
            lambda e: (
                self.undo()
                if not isinstance(self.focus_get(), (tk.Entry, tk.Spinbox, ttk.Entry))
                else None
            ),
        )
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.drop)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_home()
        self.poll_id = self.after(80, self.poll)

    @property
    def session(self):
        return self.sessions[self.mode]

    def label(self, parent, text, size=11, bold=False, color=INK, bg=WHITE):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            bg=bg,
            fg=color,
            justify="left",
        )

    def button(self, parent, text, command, accent=False, small=False):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10 if small else 11, "bold"),
            bg=RED if accent else WHITE,
            fg=WHITE if accent else INK,
            activebackground="#d7232b" if accent else "#eeeef4",
            activeforeground=WHITE if accent else INK,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=9,
            takefocus=True,
            highlightthickness=1,
            highlightcolor=RED,
        )
        button.bind("<Return>", lambda e: button.invoke())
        return button

    def clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.images, self.cards, self.card_badges = [], {}, {}

    def tool_menu(self, button, modes):
        if self.busy:
            return
        menu = tk.Menu(self, tearoff=False, font=("Segoe UI", 11))
        for mode in modes:
            menu.add_command(label=mode, command=lambda m=mode: self.change(m))
        menu.tk_popup(
            button.winfo_rootx(), button.winfo_rooty() + button.winfo_height()
        )

    def scroll_area(self, parent, bg=BG):
        wrap = tk.Frame(parent, bg=bg)
        canvas = tk.Canvas(wrap, bg=bg, highlightthickness=0)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        content = tk.Frame(canvas, bg=bg)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind(
            "<Configure>", lambda e: canvas.itemconfigure(window, width=e.width)
        )
        content.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        return wrap, canvas, content

    def wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except KeyError:
            return
        while widget:
            if isinstance(widget, tk.Canvas):
                widget.yview_scroll(-int(event.delta / 120), "units")
                return "break"
            widget = widget.master

    def reveal_focus(self, event):
        widget = event.widget
        if not isinstance(widget, tk.Misc):
            return
        ancestor = widget.master
        while ancestor and not isinstance(ancestor, tk.Canvas):
            ancestor = ancestor.master
        if ancestor:
            top = widget.winfo_rooty() - ancestor.winfo_rooty()
            bottom = top + widget.winfo_height()
            bounds = ancestor.bbox("all")
            if bounds and bounds[3] and (top < 0 or bottom > ancestor.winfo_height()):
                offset = top if top < 0 else bottom - ancestor.winfo_height()
                ancestor.yview_moveto(max(0, ancestor.canvasy(0) + offset) / bounds[3])

    def show_home(self, category="All"):
        if self.busy:
            return
        self.generation += 1
        self.loading = False
        self.home_active = True
        self.clear_body()
        for button in self.nav.values():
            button.config(fg=INK)
        self.label(
            self.body, "Your PDFs. A simpler way to work.", 30, True, bg=BG
        ).pack(pady=(28, 8))
        self.label(
            self.body,
            "Choose a tool, add your files, and make it yours. Everything stays on your computer.",
            15,
            bg=BG,
        ).pack(pady=(0, 25))
        filters = tk.Frame(self.body, bg=BG)
        filters.pack()
        for name in ["All", "Organize PDF", "Optimize PDF", "Convert PDF", "Edit PDF"]:
            button = self.button(filters, name, lambda c=name: self.show_home(c))
            button.config(
                bg=INK if name == category else WHITE,
                fg=WHITE if name == category else INK,
            )
            button.pack(side="left", padx=6)
        wrap, canvas, grid = self.scroll_area(self.body)
        wrap.pack(fill="both", expand=True, padx=26, pady=24)
        cards = []
        for mode, (group, description, color, icon) in TOOLS.items():
            if category not in ("All", group):
                continue
            suffix = "\nResume your task" if self.sessions[mode].files else ""
            card = self.button(
                grid,
                f"{icon}  {mode}\n\n{description}{suffix}",
                lambda m=mode: self.change(m),
            )
            card.config(
                anchor="nw",
                justify="left",
                wraplength=245,
                font=("Segoe UI", 13),
                height=7,
                padx=22,
                pady=20,
            )
            cards.append(card)

        def layout(event):
            columns = max(2, min(4, event.width // 280))
            for c in range(4):
                grid.grid_columnconfigure(
                    c, weight=1 if c < columns else 0, uniform="home"
                )
            for i, card in enumerate(cards):
                card.grid(
                    row=i // columns, column=i % columns, sticky="nsew", padx=9, pady=9
                )
                card.config(wraplength=max(180, event.width // columns - 70))
            canvas.configure(scrollregion=canvas.bbox("all"))

        grid.bind("<Configure>", layout)
        self.status.set(
            "7 working tools · Ctrl+O to import · Ctrl+Z to undo changes inside a tool."
        )

    def change(self, mode):
        if self.busy:
            return
        self.mode = {"Delete pages": "Remove pages", "Rotate pages": "Rotate PDF"}.get(
            mode, mode
        )
        self.home_active = False
        self.generation += 1
        self.loading = False
        if self.session.result:
            self.show_result()
        else:
            self.refresh()

    def new_task(self):
        if self.busy or not self.resolve_unsaved(self.session):
            return
        self.sessions[self.mode] = Session(self.mode)
        self.refresh()

    def resolve_unsaved(self, session):
        if session.result and not session.result["saved"]:
            choice = messagebox.askyesnocancel(
                "Save your result?",
                f"Save the {session.mode} result?\nYes: save · No: discard · Cancel: keep working.",
                parent=self,
            )
            if choice is None:
                return False
            if choice:
                return self.save_result(session)
        return True

    def add(self):
        if self.busy or self.loading or self.home_active:
            return
        types = (
            [("Images", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff")]
            if self.mode == "Images to PDF"
            else [("PDF files", "*.pdf")]
        )
        if self.mode in BATCH:
            files = filedialog.askopenfilenames(
                parent=self, title="Add files", filetypes=types
            )
        else:
            path = filedialog.askopenfilename(
                parent=self,
                title="Replace PDF" if self.session.files else "Select PDF",
                filetypes=types,
            )
            files = [path] if path else []
        self.import_files(files)

    def drop(self, event):
        if self.home_active:
            self.status.set(
                "Choose a tool first, then drop your files onto its workspace."
            )
            return "none"
        self.import_files(list(self.tk.splitlist(event.data)))
        return "copy"

    def import_files(self, files):
        if self.busy or self.loading or not files:
            return
        if self.mode not in BATCH and len(files) != 1:
            messagebox.showinfo(
                "Choose one PDF",
                "This tool works on one PDF at a time. No files were replaced.",
                parent=self,
            )
            return
        s = self.session
        if self.mode in BATCH:
            s.checkpoint()
            s.files.extend(str(Path(path).resolve()) for path in files)
        else:
            if not self.resolve_unsaved(s):
                return
            self.sessions[self.mode] = Session(
                self.mode, files=[str(Path(files[0]).resolve())]
            )
        self.session.offset = 0
        self.refresh()

    def refresh(self):
        self.home_active = False
        self.generation += 1
        self.loading = bool(self.session.files)
        s, generation = self.session, self.generation
        s.loaded = False
        self.render_work()
        if not s.files:
            self.loading = False
            return
        request = deepcopy(s)

        def load():
            counts, errors, previews = [], {}, []
            for i, path in enumerate(request.files):
                try:
                    if request.mode == "Images to PDF":
                        with Image.open(path) as source:
                            image = ImageOps.exif_transpose(source).convert("RGB")
                            counts.append(1)
                            if request.offset <= i < request.offset + 12:
                                width, height = image_page_size(
                                    image, request.page_size, request.orientation
                                )
                                scale = min(160 / width, 190 / height)
                                page_image = Image.new(
                                    "RGB",
                                    (
                                        max(1, int(width * scale)),
                                        max(1, int(height * scale)),
                                    ),
                                    "white",
                                )
                                try:
                                    margin = max(0, int(request.margin or "0")) * scale
                                except ValueError:
                                    margin = 0
                                image.thumbnail(
                                    (
                                        max(1, int(width * scale - 2 * margin)),
                                        max(1, int(height * scale - 2 * margin)),
                                    )
                                )
                                page_image.paste(
                                    image,
                                    (
                                        (page_image.width - image.width) // 2,
                                        (page_image.height - image.height) // 2,
                                    ),
                                )
                                previews.append((i, page_image))
                    else:
                        with pymupdf.open(path) as doc:
                            if not doc.is_pdf:
                                raise ValueError("Choose a PDF document.")
                            if doc.needs_pass:
                                raise ValueError(
                                    "Password protected. Choose an unlocked copy."
                                )
                            if not len(doc):
                                raise ValueError("This PDF contains no pages.")
                            counts.append(len(doc))
                            indices = (
                                [0]
                                if request.mode in BATCH
                                else (request.order or list(range(len(doc))))[
                                    request.offset : request.offset + 12
                                ]
                            )
                            for page_index in indices:
                                if (
                                    request.mode in BATCH
                                    and not request.offset <= i < request.offset + 12
                                ):
                                    continue
                                previews.append(
                                    (
                                        i if request.mode in BATCH else page_index,
                                        self.thumbnail(doc[page_index]),
                                    )
                                )
                except Exception as error:
                    if len(counts) <= i:
                        counts.append(0)
                    errors[i] = (
                        "Password protected. Choose an unlocked copy."
                        if "Password protected" in str(error)
                        else "Cannot read this file. Remove it or choose a valid "
                        + ("image." if request.mode == "Images to PDF" else "PDF.")
                    )
            self.events.put(("preview", generation, counts, errors, previews))

        self.preview_pool.submit(load)

    @staticmethod
    def thumbnail(page):
        scale = min(160 / page.rect.width, 190 / page.rect.height)
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False
        )
        return Image.open(BytesIO(pix.tobytes("png"))).copy()

    def receive_previews(self, counts, errors, previews):
        s = self.session
        s.counts, s.errors, s.loaded = counts, errors, True
        self.loading = False
        if self.mode not in BATCH and not s.order and s.page_count:
            s.order = list(range(s.page_count))
            s.ranges = [("1", str(s.page_count))]
        self.preview_data = previews
        self.render_work()
        self.paint_gallery()
        self.update_action()

    def render_work(self):
        self.clear_body()
        s = self.session
        for name, button in self.nav.items():
            button.config(fg=RED if name == self.mode else INK)
        if not s.files:
            self.label(self.body, self.mode, 34, True, bg=BG).pack(pady=(55, 12))
            self.label(self.body, TOOLS[self.mode][1], 17, bg=BG).pack(pady=10)
            select = self.button(
                self.body,
                (
                    "Select images"
                    if self.mode == "Images to PDF"
                    else (
                        "Select PDF files" if self.mode in BATCH else "Select PDF file"
                    )
                ),
                self.add,
                accent=True,
            )
            select.config(font=("Segoe UI", 20, "bold"), padx=65, pady=22)
            select.pack(pady=25)
            self.label(
                self.body, "or drop your files here", 12, color=MUTED, bg=BG
            ).pack()
            if s.history:
                self.button(self.body, "Undo last change", self.undo).pack(pady=15)
            self.status.set("Choose files from your computer. Originals are preserved.")
            return
        self.sidebar = tk.Frame(self.body, bg=WHITE, width=355)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)
        self.workspace = tk.Frame(self.body, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)
        toolbar = tk.Frame(self.workspace, bg=BG)
        toolbar.pack(fill="x", padx=16, pady=12)
        self.button(toolbar, "← Tools", self.show_home, small=True).pack(side="left")
        self.button(toolbar, "New task", self.new_task, small=True).pack(
            side="left", padx=5
        )
        self.button(
            toolbar,
            "+ Add files" if self.mode in BATCH else "Replace PDF",
            self.add,
            small=True,
        ).pack(side="right")
        if s.result:
            self.button(toolbar, "Last result", self.show_result, small=True).pack(
                side="right", padx=4
            )
        controls = tk.Frame(self.workspace, bg=BG)
        controls.pack(fill="x", padx=20, pady=(0, 8))
        self.button(controls, "Undo", self.undo, small=True).pack(side="left")
        if self.mode in ("Merge PDF", "Images to PDF"):
            self.button(
                controls, "Sort A–Z", lambda: self.sort_files(False), small=True
            ).pack(side="left", padx=3)
            self.button(
                controls, "Sort Z–A", lambda: self.sort_files(True), small=True
            ).pack(side="left")
        detail = (
            f"{len(s.files)} files"
            if self.mode in BATCH
            else f"{Path(s.files[0]).name} · {s.page_count} pages"
        )
        info = self.label(controls, detail, 10, color=MUTED, bg=BG)
        info.config(wraplength=350)
        info.pack(side="right")
        self.pager = tk.Frame(self.workspace, bg=BG)
        self.pager.pack(side="bottom", fill="x", padx=22, pady=10)
        wrap, self.canvas, self.gallery = self.scroll_area(self.workspace)
        wrap.pack(fill="both", expand=True, padx=10)
        if self.loading:
            self.label(
                self.gallery, "Checking files and loading previews…", 15, bg=BG
            ).pack(pady=80)
        self.render_sidebar()

    def variable(self, key, boolean=False):
        variable = (
            tk.BooleanVar(value=getattr(self.session, key))
            if boolean
            else tk.StringVar(value=getattr(self.session, key))
        )

        def changed(*args):
            if not self.syncing:
                setattr(self.session, key, variable.get())
                self.update_action()

        variable.trace_add("write", changed)
        return variable

    def render_sidebar(self):
        s = self.session
        self.label(
            self.sidebar,
            "Compression level" if self.mode == "Compress PDF" else self.mode,
            23,
            True,
        ).pack(pady=(16, 12))
        bottom = tk.Frame(self.sidebar, bg=WHITE)
        bottom.pack(side="bottom", fill="x", padx=20, pady=18)
        self.feedback = tk.Label(
            bottom,
            textvariable=self.validation,
            wraplength=310,
            bg=WHITE,
            fg=RED,
            justify="left",
            font=("Segoe UI", 10),
        )
        self.feedback.pack(fill="x", pady=(0, 10))
        self.action = self.button(bottom, self.mode + "  →", self.run, accent=True)
        self.action.config(font=("Segoe UI", 16, "bold"), pady=17)
        self.action.pack(fill="x")
        wrap, _, self.options = self.scroll_area(self.sidebar, WHITE)
        wrap.pack(fill="both", expand=True, padx=18)
        if self.mode == "Split PDF":
            tabs = tk.Frame(self.options, bg=WHITE)
            tabs.pack(fill="x", pady=5)
            for mode in ["Custom", "Fixed", "Pages"]:
                button = self.button(
                    tabs, mode, lambda m=mode: self.set_split(m), small=True
                )
                button.config(
                    fg=RED if s.split_mode == mode else INK,
                    bg="#ffeded" if s.split_mode == mode else BG,
                )
                button.pack(side="left", expand=True, fill="x", padx=2)
            if s.split_mode == "Custom":
                self.range_vars = []
                self.range_notes = []
                for i, (a, b) in enumerate(s.ranges):
                    row = tk.Frame(self.options, bg=WHITE)
                    row.pack(fill="x", pady=8)
                    self.label(row, f"Range {i+1}", 10, True).pack(anchor="w")
                    fields = tk.Frame(row, bg=WHITE)
                    fields.pack(fill="x")
                    pair = (tk.StringVar(value=a), tk.StringVar(value=b))
                    self.range_vars.append(pair)
                    for text, variable in zip(["From", "to"], pair):
                        self.label(fields, text, 10).pack(side="left")
                        tk.Spinbox(
                            fields,
                            from_=1,
                            to=max(1, s.page_count),
                            textvariable=variable,
                            width=5,
                            font=("Segoe UI", 12),
                        ).pack(side="left", padx=5, pady=4)
                        variable.trace_add("write", lambda *args: self.ranges_changed())
                    self.button(
                        fields,
                        "×",
                        lambda index=i: self.delete_range(index),
                        small=True,
                    ).pack(side="right")
                    note = self.label(row, "", 9, color=RED)
                    note.config(wraplength=285)
                    note.pack(anchor="w")
                    self.range_notes.append(note)
                self.button(self.options, "+ Add range", self.add_range).pack(
                    fill="x", pady=8
                )
            elif s.split_mode == "Fixed":
                self.label(self.options, "Pages per file", 12, True).pack(
                    anchor="w", pady=(18, 8)
                )
                self.fixed_var = self.variable("fixed")
                tk.Spinbox(
                    self.options,
                    from_=1,
                    to=max(1, s.page_count),
                    textvariable=self.fixed_var,
                    font=("Segoe UI", 14),
                    width=8,
                ).pack(anchor="w", pady=8)
            else:
                self.label(self.options, "Pages to extract", 12, True).pack(
                    anchor="w", pady=(15, 8)
                )
                self.pages_var = self.variable("page_text")
                self.pages_var.trace_add("write", lambda *args: self.pages_changed())
                tk.Entry(
                    self.options, textvariable=self.pages_var, font=("Segoe UI", 12)
                ).pack(fill="x")
                self.label(self.options, "Example: 1,3-5", 9, color=MUTED).pack(
                    anchor="w", pady=4
                )
                self.button(self.options, "Select all pages", self.select_all).pack(
                    fill="x", pady=5
                )
                self.button(self.options, "Clear selection", self.clear_selection).pack(
                    fill="x"
                )
            self.combine_var = self.variable("combine", True)
            tk.Checkbutton(
                self.options,
                text="Merge output into one PDF",
                variable=self.combine_var,
                bg=WHITE,
                font=("Segoe UI", 11),
            ).pack(anchor="w", pady=15)
        elif self.mode == "Compress PDF":
            self.compression_var = self.variable("compression")
            for title, note in [
                ("Extreme compression", "Smaller files, lower image quality"),
                ("Recommended compression", "Balanced size and image quality"),
                ("Less compression", "Higher image quality"),
            ]:
                tk.Radiobutton(
                    self.options,
                    text=title,
                    variable=self.compression_var,
                    value=title,
                    bg=WHITE,
                    fg=RED,
                    font=("Segoe UI", 12),
                    anchor="w",
                ).pack(fill="x", pady=(16, 4))
                self.label(self.options, note, 10, color=MUTED).pack(
                    anchor="w", padx=20
                )
            note = self.label(
                self.options,
                "Text stays sharp. Images may lose detail. Originals are preserved.",
                10,
                color=MUTED,
            )
            note.config(wraplength=290)
            note.pack(pady=20)
        elif self.mode in ("Organize PDF", "Remove pages", "Rotate PDF"):
            instruction = {
                "Organize PDF": "Drag pages to reorder. Mark pages to remove, or rotate them. Undo restores the previous change.",
                "Remove pages": "Click a page to mark it for removal. Click again to restore it.",
                "Rotate PDF": "Use ↻ on a page, or select pages and apply a rotation. The preview shows the result.",
            }[self.mode]
            label = self.label(self.options, instruction, 12)
            label.config(wraplength=295)
            label.pack(pady=15)
            if self.mode == "Remove pages":
                self.button(self.options, "Restore all pages", self.restore_all).pack(
                    fill="x"
                )
            else:
                self.button(self.options, "Select all pages", self.select_all).pack(
                    fill="x", pady=4
                )
                self.button(self.options, "Clear selection", self.clear_selection).pack(
                    fill="x", pady=4
                )
                self.button(
                    self.options, "Rotate selected 90°", self.rotate_selected
                ).pack(fill="x", pady=4)
                self.button(
                    self.options, "Rotate all 90°", lambda: self.rotate_selected(True)
                ).pack(fill="x", pady=4)
                if self.mode == "Organize PDF":
                    self.button(
                        self.options, "Restore all pages", self.restore_all
                    ).pack(fill="x", pady=4)
        elif self.mode == "Images to PDF":
            for key, title, values in [
                ("page_size", "Page size", ["A4", "Letter", "Original"]),
                ("orientation", "Orientation", ["Portrait", "Landscape"]),
            ]:
                self.label(self.options, title, 12, True).pack(anchor="w", pady=(14, 7))
                var = self.variable(key)
                combo = ttk.Combobox(
                    self.options,
                    textvariable=var,
                    values=values,
                    state="readonly",
                    font=("Segoe UI", 12),
                )
                combo._var = var
                combo.pack(fill="x")
                combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
            self.label(self.options, "Margins (points)", 12, True).pack(
                anchor="w", pady=(18, 6)
            )
            self.margin_var = self.variable("margin")
            tk.Spinbox(
                self.options,
                from_=0,
                to=100,
                textvariable=self.margin_var,
                font=("Segoe UI", 12),
                width=8,
            ).pack(anchor="w")
            self.button(self.options, "Update preview", self.refresh).pack(
                fill="x", pady=12
            )
            self.label(
                self.options,
                "Original size follows the image aspect ratio.",
                9,
                color=MUTED,
            ).pack(anchor="w")
        else:
            label = self.label(
                self.options,
                "Drag files to arrange the output order. Use the arrows to move between positions, or sort by name.",
                12,
            )
            label.config(wraplength=295)
            label.pack(pady=15)
        self.update_action()

    def set_split(self, mode):
        if self.busy or self.loading:
            return
        self.session.split_mode = mode
        self.render_work()
        self.paint_gallery()

    def ranges_changed(self):
        self.session.ranges = [(a.get(), b.get()) for a, b in self.range_vars]
        for (a, b), note in zip(self.session.ranges, self.range_notes):
            try:
                valid = 1 <= int(a) <= int(b) <= self.session.page_count
            except ValueError:
                valid = False
            note.config(
                text=(
                    ""
                    if valid
                    else f"Use pages 1–{self.session.page_count}, with start ≤ end."
                )
            )
        self.paint_selection()
        self.update_action()

    def add_range(self):
        if self.loading or self.busy:
            return
        self.session.ranges.append(("1", str(self.session.page_count)))
        self.render_work()
        self.paint_gallery()

    def delete_range(self, index):
        if self.loading or self.busy:
            return
        self.session.ranges.pop(index)
        self.render_work()
        self.paint_gallery()

    def pages_changed(self):
        if self.syncing:
            return
        self.session.page_text = self.pages_var.get()
        try:
            self.session.selected = (
                set(selection(self.session.page_text, self.session.page_count))
                if self.session.page_text.strip()
                else set()
            )
        except ValueError:
            self.session.selected = set()
        self.paint_selection()
        self.update_action()

    def update_action(self):
        if not hasattr(self, "action") or not self.action.winfo_exists():
            return
        try:
            if self.busy:
                raise ValueError("Processing your files…")
            if self.loading:
                raise ValueError("Checking files and loading previews…")
            contract = self.session.contract()
            message = (
                f"Output: {contract['count']} PDF file(s), {contract['pages']} pages"
                + (" in a ZIP." if contract["count"] > 1 else ".")
            )
            if contract["warning"]:
                message += "\n" + contract["warning"]
            self.validation.set(message)
            self.feedback.config(fg=INK)
            self.action.config(state="normal")
        except (ValueError, TypeError) as error:
            self.validation.set(str(error))
            self.feedback.config(fg=MUTED if self.loading else RED)
            self.action.config(state="disabled")

    def paint_gallery(self):
        if (
            self.loading
            or not hasattr(self, "gallery")
            or not self.gallery.winfo_exists()
        ):
            return
        s = self.session
        self.cards, self.card_badges, self.images = {}, {}, []
        for child in self.gallery.winfo_children():
            child.destroy()
        for child in self.pager.winfo_children():
            child.destroy()
        items = list(range(len(s.files))) if self.mode in BATCH or s.errors else s.order
        visible = items[s.offset : s.offset + 12]
        thumbnails = dict(self.preview_data)
        for position, index in enumerate(visible):
            frame = tk.Frame(
                self.gallery,
                bg=WHITE,
                highlightthickness=2,
                highlightbackground="#dddde6",
                padx=10,
                pady=10,
            )
            frame.grid(
                row=position // 3, column=position % 3, padx=9, pady=9, sticky="nsew"
            )
            frame._card_index = index
            self.cards[index] = frame
            file_card = self.mode in BATCH or bool(s.errors)
            error = s.errors.get(index if file_card else 0)
            order = s.offset + position + 1
            name = Path(s.files[index]).name if file_card else f"Page {index+1}"
            heading = self.label(
                frame,
                (
                    f"{order}. {name}"
                    if file_card or self.mode == "Organize PDF"
                    else name
                ),
                10,
                True,
            )
            heading.config(wraplength=175)
            heading.pack()
            image = thumbnails.get(index)
            if error:
                preview = self.label(frame, "⚠\n" + error, 11, color=RED)
                preview.config(wraplength=165, height=10)
            elif image:
                rotation = 0 if file_card else s.rotations.get(index, 0)
                image = image.rotate(-rotation, expand=True)
                image.thumbnail((160, 190))
                photo = ImageTk.PhotoImage(image)
                self.images.append(photo)
                preview = tk.Label(frame, image=photo, bg=WHITE, width=175, height=195)
            else:
                preview = self.label(frame, "Preview unavailable", 11, color=MUTED)
            preview.pack(pady=6)
            badge = self.label(frame, "", 10, color=RED)
            badge.pack()
            self.card_badges[index] = badge
            if file_card:
                if not error:
                    self.label(
                        frame,
                        f"{s.counts[index]} page(s) · {size_text(Path(s.files[index]).stat().st_size)}",
                        9,
                        color=MUTED,
                    ).pack()
                bar = tk.Frame(frame, bg=WHITE)
                bar.pack()
                if self.mode in ("Merge PDF", "Images to PDF"):
                    for text, delta in [("←", -1), ("→", 1)]:
                        self.button(
                            bar,
                            text,
                            lambda i=index, d=delta: self.move(i, d),
                            small=True,
                        ).pack(side="left")
                self.button(
                    bar, "Remove", lambda i=index: self.remove_file(i), small=True
                ).pack(side="left")
            else:
                bar = tk.Frame(frame, bg=WHITE)
                bar.pack()
                if self.mode == "Organize PDF":
                    for text, delta in [("←", -1), ("→", 1)]:
                        self.button(
                            bar,
                            text,
                            lambda i=index, d=delta: self.move(i, d),
                            small=True,
                        ).pack(side="left")
                if self.mode in ("Organize PDF", "Rotate PDF"):
                    self.button(
                        bar, "↻", lambda i=index: self.rotate_page(i), small=True
                    ).pack(side="left")
                if self.mode in ("Organize PDF", "Remove pages"):
                    self.button(
                        bar,
                        "Restore" if index in s.removed else "×",
                        lambda i=index: self.mark_removed(i),
                        small=True,
                    ).pack(side="left")
                self.button(
                    frame, "Preview", lambda i=index: self.open_preview(i), small=True
                ).pack()
            interactive = self.mode in (
                "Merge PDF",
                "Images to PDF",
                "Organize PDF",
                "Remove pages",
                "Rotate PDF",
            ) or (self.mode == "Split PDF" and s.split_mode == "Pages")
            for widget in (frame, preview, heading):
                widget.configure(cursor="hand2" if interactive else "arrow")
                widget.bind("<ButtonPress-1>", lambda e, i=index: self.drag_start(e, i))
                widget.bind("<ButtonRelease-1>", lambda e, i=index: self.drag_end(e, i))
            frame.config(takefocus=interactive)
            frame.bind("<Return>", lambda e, i=index: self.toggle(i))
            frame.bind("<space>", lambda e, i=index: self.toggle(i))
            frame.bind("<Alt-Left>", lambda e, i=index: self.move(i, -1))
            frame.bind("<Alt-Right>", lambda e, i=index: self.move(i, 1))
            frame.bind(
                "<FocusIn>", lambda e, c=frame: c.config(highlightbackground=INK)
            )
            frame.bind("<FocusOut>", lambda e: self.paint_selection())
        for col in range(3):
            self.gallery.grid_columnconfigure(col, weight=1, uniform="pages")
        total = len(items)
        if s.offset:
            self.button(
                self.pager, "← Previous", lambda: self.paginate(-12), small=True
            ).pack(side="left")
        self.label(
            self.pager, f"{s.offset+1}–{min(s.offset+12,total)} of {total}", 10, bg=BG
        ).pack(side="left", padx=12)
        if s.offset + 12 < total:
            self.button(
                self.pager, "Next →", lambda: self.paginate(12), small=True
            ).pack(side="right")
        self.paint_selection()
        self.status.set(
            "Drop files here to add them."
            if self.mode in BATCH
            else "Changes affect your result. Your original PDF stays unchanged."
        )

    def paint_selection(self):
        s = self.session
        marked = s.selected
        if self.mode == "Split PDF" and s.split_mode != "Pages":
            try:
                marked = {i for group in s.groups() for i in group}
            except ValueError:
                marked = set()
        for index, card in self.cards.items():
            if not card.winfo_exists():
                continue
            removed = index in s.removed
            card.config(
                highlightbackground=(
                    RED if removed else ("#39a66d" if index in marked else "#dddde6")
                )
            )
            self.card_badges[index].config(
                text=(
                    "× Will be removed"
                    if removed
                    else (
                        "✓ Selected"
                        if index in marked
                        else (
                            f"↻ {s.rotations[index]}°" if s.rotations.get(index) else ""
                        )
                    )
                )
            )

    def toggle(self, index):
        if self.busy or self.loading:
            return
        s = self.session
        if self.mode == "Remove pages":
            self.mark_removed(index)
            return
        if self.mode not in ("Rotate PDF", "Organize PDF") and not (
            self.mode == "Split PDF" and s.split_mode == "Pages"
        ):
            return
        s.selected.symmetric_difference_update({index})
        if self.mode == "Split PDF":
            s.page_text = ",".join(str(i + 1) for i in sorted(s.selected))
            self.syncing = True
            self.pages_var.set(s.page_text)
            self.syncing = False
        self.paint_selection()
        self.update_action()

    def select_all(self):
        if self.loading or self.busy:
            return
        s = self.session
        s.selected = set(range(s.page_count))
        if self.mode == "Split PDF":
            s.page_text = f"1-{s.page_count}"
            self.pages_var.set(s.page_text)
        self.paint_selection()
        self.update_action()

    def clear_selection(self):
        if self.loading or self.busy:
            return
        self.session.selected.clear()
        if self.mode == "Split PDF":
            self.session.page_text = ""
            self.pages_var.set("")
        self.paint_selection()
        self.update_action()

    def mark_removed(self, index):
        if self.loading or self.busy:
            return
        self.session.checkpoint()
        self.session.removed.symmetric_difference_update({index})
        self.paint_gallery()
        self.update_action()

    def restore_all(self):
        if self.loading or self.busy:
            return
        self.session.checkpoint()
        self.session.removed.clear()
        self.paint_gallery()
        self.update_action()

    def rotate_page(self, index):
        if self.loading or self.busy:
            return
        self.session.checkpoint()
        self.session.rotations[index] = (
            self.session.rotations.get(index, 0) + 90
        ) % 360
        self.paint_gallery()
        self.update_action()

    def rotate_selected(self, all_pages=False):
        if self.loading or self.busy:
            return
        s = self.session
        indices = range(s.page_count) if all_pages else s.selected
        if not indices:
            self.status.set("Select pages first, or use Rotate all.")
            return
        s.checkpoint()
        for i in indices:
            s.rotations[i] = (s.rotations.get(i, 0) + 90) % 360
        self.paint_gallery()
        self.update_action()

    def drag_start(self, event, index):
        self.drag_origin = (index, event.x_root, event.y_root)
        event.widget.focus_set()

    def drag_end(self, event, index):
        if not hasattr(self, "drag_origin"):
            return
        source, x, y = self.drag_origin
        if abs(event.x_root - x) + abs(event.y_root - y) < 8:
            self.toggle(index)
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget and not hasattr(widget, "_card_index"):
            widget = widget.master
        if widget and self.mode in ("Merge PDF", "Images to PDF", "Organize PDF"):
            self.reorder(source, widget._card_index)

    def reorder(self, source, target):
        if self.mode not in ("Merge PDF", "Images to PDF", "Organize PDF"):
            return
        if self.loading or self.busy or source == target:
            return
        s = self.session
        s.checkpoint()
        if self.mode in BATCH:
            value = s.files.pop(source)
            s.files.insert(target, value)
        else:
            old, new = s.order.index(source), s.order.index(target)
            value = s.order.pop(old)
            s.order.insert(new, value)
        self.refresh()

    def move(self, index, delta):
        if self.mode not in ("Merge PDF", "Images to PDF", "Organize PDF"):
            return
        if self.loading or self.busy:
            return
        items = (
            list(range(len(self.session.files)))
            if self.mode in BATCH
            else self.session.order
        )
        pos = items.index(index)
        if 0 <= pos + delta < len(items):
            self.reorder(index, items[pos + delta])

    def sort_files(self, reverse):
        if self.loading or self.busy:
            return
        self.session.checkpoint()
        self.session.files.sort(key=lambda p: Path(p).name.casefold(), reverse=reverse)
        self.refresh()

    def remove_file(self, index):
        if self.loading or self.busy:
            return
        s = self.session
        s.checkpoint()
        s.files.pop(index)
        s.offset = max(0, min(s.offset, ((len(s.files) - 1) // 12) * 12))
        self.refresh()

    def undo(self):
        if self.home_active or self.loading or self.busy:
            return
        if self.session.undo():
            self.refresh()

    def paginate(self, delta):
        if self.loading or self.busy:
            return
        self.session.offset = max(0, self.session.offset + delta)
        self.refresh()

    def open_preview(self, index):
        try:
            with pymupdf.open(self.session.files[0]) as doc:
                page = doc[index]
                scale = min(700 / page.rect.width, 650 / page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                image = Image.open(BytesIO(pix.tobytes("png"))).rotate(
                    -self.session.rotations.get(index, 0), expand=True
                )
            dialog = tk.Toplevel(self)
            dialog.title(f"Page {index+1} preview")
            dialog.configure(bg=BG)
            photo = ImageTk.PhotoImage(image)
            dialog.photo = photo
            tk.Label(dialog, image=photo, bg=BG).pack(padx=12, pady=12)
            self.button(dialog, "Close", dialog.destroy).pack(pady=8)
            dialog.transient(self)
        except Exception as error:
            messagebox.showerror("Preview unavailable", str(error), parent=self)

    def run(self):
        if self.busy or self.loading:
            return
        try:
            request = self.session.request()
        except ValueError:
            self.update_action()
            return
        if not self.resolve_unsaved(self.session):
            return
        folder = tempfile.mkdtemp(prefix="result-", dir=self.temporary.name)
        self.job_folder = folder
        self.job = mp.get_context("spawn").Process(
            target=run_job, args=(request, folder), daemon=True
        )
        self.busy = True
        try:
            self.job.start()
        except Exception as error:
            self.busy = False
            self.job = None
            messagebox.showerror("Could not start processing", str(error), parent=self)
            return
        self.render_processing()

    def render_processing(self):
        self.clear_body()
        self.label(self.body, self.mode + "…", 30, True, bg=BG).pack(pady=(100, 20))
        tk.Label(
            self.body, textvariable=self.status, font=("Segoe UI", 14), bg=BG, fg=INK
        ).pack(pady=15)
        progress = ttk.Progressbar(self.body, mode="indeterminate", length=420)
        progress.pack(pady=18)
        progress.start(12)
        self.button(self.body, "Cancel processing", self.cancel_job).pack(pady=20)
        self.status.set("Preparing your result…")

    def cancel_job(self):
        if not self.busy:
            return
        if self.job.is_alive():
            self.job.terminate()
        self.job.join(timeout=3)
        self.job = None
        self.busy = False
        self.refresh()
        self.status.set("Processing cancelled. Your inputs and settings are preserved.")

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if (
                    event[0] == "preview"
                    and event[1] == self.generation
                    and not self.home_active
                ):
                    self.receive_previews(*event[2:])
        except queue.Empty:
            pass
        if self.busy and self.job:
            status_file = Path(self.job_folder) / "status.json"
            try:
                state = json.loads(status_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                state = {}
            # If the worker exited after the first read, pick up its final status.
            if self.job.exitcode is not None:
                try:
                    state = json.loads(status_file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            if state.get("state") in ("done", "error"):
                self.job.join(timeout=0.2)
                self.busy = False
                self.job = None
                if state["state"] == "done":
                    self.session.result = state["result"]
                    self.show_result()
                else:
                    self.refresh()
                    messagebox.showerror(
                        "Could not process files",
                        state["message"]
                        + "\nYour inputs are preserved. Fix the problem and retry.",
                        parent=self,
                    )
            elif self.job.exitcode is not None:
                self.busy = False
                self.job = None
                self.refresh()
                messagebox.showerror(
                    "Processing interrupted",
                    "The worker stopped unexpectedly. Your files and settings are preserved. Please retry.",
                    parent=self,
                )
            elif state.get("message"):
                self.status.set(state["message"])
        self.poll_id = self.after(80, self.poll)

    def show_result(self):
        result = self.session.result
        if not result:
            return
        self.generation += 1
        self.loading = False
        self.home_active = False
        self.clear_body()
        self.label(self.body, "Your result is ready", 30, True, bg=BG).pack(
            pady=(35, 10)
        )
        self.label(
            self.body,
            f"{len(result['pdfs'])} PDF file(s) · {result['pages']} pages · {size_text(Path(result['path']).stat().st_size)}",
            14,
            bg=BG,
        ).pack(pady=10)
        self.button(self.body, "Save result", self.save_result, accent=True).pack(
            pady=14
        )
        actions = tk.Frame(self.body, bg=BG)
        actions.pack(pady=8)
        self.button(
            actions,
            "Open result",
            lambda: self.open_file(result["saved"] or result["path"]),
        ).pack(side="left", padx=5)
        self.button(
            actions,
            "Show in folder",
            lambda: self.open_file(str(Path(result["saved"] or result["path"]).parent)),
        ).pack(side="left", padx=5)
        self.button(actions, "← Change settings", self.refresh).pack(
            side="left", padx=5
        )
        self.button(actions, "New task", self.new_task).pack(side="left", padx=5)
        continuation = tk.Frame(self.body, bg=BG)
        continuation.pack(side="bottom", pady=20)
        self.label(continuation, "Continue with these PDFs:", 12, True, bg=BG).pack(
            pady=8
        )
        row = tk.Frame(continuation, bg=BG)
        row.pack()
        for mode in ["Merge PDF", "Split PDF", "Compress PDF", "Organize PDF"]:
            if len(result["pdfs"]) == 1 or mode in BATCH:
                self.button(row, mode, lambda m=mode: self.continue_with(m)).pack(
                    side="left", padx=5
                )
        if result["stats"]:
            wrap, _, content = self.scroll_area(self.body)
            wrap.pack(fill="both", expand=True, padx=80, pady=12)
            for stat in result["stats"]:
                gain = (
                    100 * (1 - stat["after"] / stat["before"]) if stat["before"] else 0
                )
                line = (
                    f"{stat['name']}\n{size_text(stat['before'])} → {size_text(stat['after'])} · "
                    + (
                        f"{gain:.1f}% smaller"
                        if stat["after"] < stat["before"]
                        else "Already optimized — no size reduction"
                    )
                )
                label = self.label(content, line, 12, bg=BG)
                label.config(wraplength=850)
                label.pack(anchor="w", pady=10)
        self.status.set(
            "Saved: " + result["saved"]
            if result["saved"]
            else "Result is ready. Save it to keep a copy before closing."
        )

    def save_result(self, session=None, destination=None):
        s = session or self.session
        result = s.result
        if not result:
            return False
        source = Path(result["path"])
        output = destination or filedialog.asksaveasfilename(
            parent=self,
            title="Save your result",
            initialfile=source.name,
            defaultextension=source.suffix,
            filetypes=[
                (
                    "ZIP archive" if source.suffix == ".zip" else "PDF document",
                    "*" + source.suffix,
                )
            ],
        )
        if not output:
            return False
        output = Path(output)
        protected = {
            Path(p).resolve() for task in self.sessions.values() for p in task.files
        }
        if output.resolve() in protected:
            messagebox.showerror(
                "Keep the original",
                "Choose a different filename to preserve your input files.",
                parent=self,
            )
            return False
        temporary = None
        try:
            handle, temporary = tempfile.mkstemp(
                dir=output.parent, suffix=source.suffix
            )
            os.close(handle)
            shutil.copyfile(source, temporary)
            os.replace(temporary, output)
            result["saved"] = str(output)
            self.status.set("Saved: " + str(output))
            return True
        except OSError as error:
            messagebox.showerror(
                "Could not save",
                str(error)
                + "\nYour result is still available. Choose another destination.",
                parent=self,
            )
            return False
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def continue_with(self, mode):
        files = list(self.session.result["pdfs"])
        if self.sessions[mode].files:
            if not messagebox.askyesno(
                "Start with this result?",
                f"Replace the current {mode} task with these result files?",
                parent=self,
            ):
                return
            if not self.resolve_unsaved(self.sessions[mode]):
                return
        self.sessions[mode] = Session(mode, files=files)
        self.mode = mode
        self.refresh()

    def open_file(self, path):
        try:
            os.startfile(path)
        except OSError as error:
            messagebox.showerror("Could not open", str(error), parent=self)

    def close(self):
        if self.busy:
            if not messagebox.askyesno(
                "Cancel processing?",
                "Cancel the current process and close PDF Studio?",
                parent=self,
            ):
                return
            self.cancel_job()
        for session in self.sessions.values():
            if not self.resolve_unsaved(session):
                return
        self.destroy()

    def destroy(self):
        if self.poll_id:
            self.after_cancel(self.poll_id)
            self.poll_id = None
        if self.job and self.job.is_alive():
            self.job.terminate()
            self.job.join(timeout=3)
        self.preview_pool.shutdown(wait=True, cancel_futures=True)
        self.temporary.cleanup()
        super().destroy()


if __name__ == "__main__":
    mp.freeze_support()
    app = App()
    if "--smoke-test" in sys.argv:
        app.withdraw()
        app.update()
        app.destroy()
        from selfcheck import check_worker

        check_worker()
    else:
        app.mainloop()
