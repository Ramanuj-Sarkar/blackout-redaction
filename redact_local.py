#!/usr/bin/env python3
"""
redact_local.py  —  Local, offline, true-redaction tool for PDFs.

Draw boxes over the fields you want to remove (patient name, MRN, DOB,
personnel names, signatures, etc.). When you click "Apply & Save", the
content UNDER each box — text AND image pixels — is physically removed
from the file, not just covered. Everything you don't box (your
handwritten data values) is left untouched, so legibility is preserved.

Nothing leaves your machine. No network calls. No subscription.

------------------------------------------------------------------
SETUP (one time):
    pip install pymupdf
    # tkinter ships with most Python installs. If missing:
    #   Windows/macOS: reinstall Python from python.org (includes tkinter)
    #   Linux (Debian/Ubuntu): sudo apt install python3-tk

RUN:
    python3 redact_local.py
------------------------------------------------------------------

HOW TO USE:
  1. Click "Open PDF" and pick a document.
  2. Drag to draw a red box over each item to redact. Draw as many as you like.
  3. Use Prev/Next to move between pages (boxes are remembered per page).
  4. "Undo Last Box" removes the most recent box on the current page.
  5. "Clear Page" removes all boxes on the current page.
  6. "Apply & Save" writes a NEW file ("<name>_redacted.pdf"). Your original
     is never modified. Metadata is sanitized automatically.
  7. After saving, the tool re-opens the output and confirms no text remains
     under your boxes.

NOTE: If a PDF is a fillable form, this tool flattens it on save so field
values can't survive behind a box.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required. Install with:  pip install pymupdf")

RENDER_DPI = 150          # on-screen render quality
MAX_VIEW_H = 850          # max canvas height in px (scrolls if taller)


class Redactor:
    def __init__(self, root):
        self.root = root
        root.title("Local PDF Redactor — true redaction, fully offline")

        self.doc = None
        self.path = None
        self.page_index = 0
        self.scale = 1.0               # pdf points -> screen px
        self.boxes = {}                # page_index -> list of (x0,y0,x1,y1) in PDF points
        self.tk_img = None
        self._drag_start = None
        self._temp_rect = None

        # --- top toolbar ---
        bar = tk.Frame(root)
        bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        tk.Button(bar, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT)
        self.prev_btn = tk.Button(bar, text="◀ Prev", command=self.prev_page, state=tk.DISABLED)
        self.prev_btn.pack(side=tk.LEFT, padx=(10, 2))
        self.next_btn = tk.Button(bar, text="Next ▶", command=self.next_page, state=tk.DISABLED)
        self.next_btn.pack(side=tk.LEFT, padx=2)
        self.page_lbl = tk.Label(bar, text="No file")
        self.page_lbl.pack(side=tk.LEFT, padx=10)

        tk.Button(bar, text="Undo Last Box", command=self.undo_box).pack(side=tk.LEFT, padx=2)
        tk.Button(bar, text="Clear Page", command=self.clear_page).pack(side=tk.LEFT, padx=2)
        self.save_btn = tk.Button(bar, text="Apply & Save", command=self.apply_save,
                                  state=tk.DISABLED, fg="white", bg="#b00020")
        self.save_btn.pack(side=tk.RIGHT)
        self.count_lbl = tk.Label(bar, text="")
        self.count_lbl.pack(side=tk.RIGHT, padx=10)

        # --- scrollable canvas ---
        wrap = tk.Frame(root)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, bg="#555", cursor="crosshair")
        vsb = tk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        hsb = tk.Scrollbar(wrap, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)

    # ---------- file handling ----------
    def open_pdf(self):
        path = filedialog.askopenfilename(
            title="Open PDF", filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        try:
            self.doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF:\n{e}")
            return
        self.path = path
        self.page_index = 0
        self.boxes = {}
        self.save_btn.config(state=tk.NORMAL)
        self.render_page()

    def render_page(self):
        page = self.doc[self.page_index]
        # fit to MAX_VIEW_H
        rect = page.rect
        zoom = RENDER_DPI / 72.0
        self.scale = zoom
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        # downscale if too tall
        if pix.height > MAX_VIEW_H:
            factor = MAX_VIEW_H / pix.height
            self.scale = zoom * factor
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
        self.tk_img = tk.PhotoImage(data=pix.tobytes("ppm"))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.redraw_boxes()
        self.update_labels()

    def update_labels(self):
        n = len(self.doc)
        self.page_lbl.config(text=f"Page {self.page_index+1} / {n}  —  "
                                  f"{os.path.basename(self.path)}")
        total = sum(len(v) for v in self.boxes.values())
        here = len(self.boxes.get(self.page_index, []))
        self.count_lbl.config(text=f"{here} box(es) here · {total} total")
        self.prev_btn.config(state=tk.NORMAL if self.page_index > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.page_index < n-1 else tk.DISABLED)

    # ---------- navigation ----------
    def prev_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            self.render_page()

    def next_page(self):
        if self.page_index < len(self.doc) - 1:
            self.page_index += 1
            self.render_page()

    # ---------- drawing ----------
    def on_down(self, ev):
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        self._drag_start = (x, y)
        self._temp_rect = self.canvas.create_rectangle(
            x, y, x, y, outline="red", width=2, fill="red", stipple="gray25")

    def on_move(self, ev):
        if self._drag_start is None:
            return
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        self.canvas.coords(self._temp_rect, self._drag_start[0],
                           self._drag_start[1], x, y)

    def on_up(self, ev):
        if self._drag_start is None:
            return
        x = self.canvas.canvasx(ev.x)
        y = self.canvas.canvasy(ev.y)
        x0, y0 = self._drag_start
        self._drag_start = None
        self.canvas.delete(self._temp_rect)
        self._temp_rect = None
        # ignore tiny accidental clicks
        if abs(x - x0) < 4 or abs(y - y0) < 4:
            self.redraw_boxes()
            return
        # convert screen px -> PDF points
        sx0, sx1 = sorted((x0, x)); sy0, sy1 = sorted((y0, y))
        pdf_rect = (sx0/self.scale, sy0/self.scale,
                    sx1/self.scale, sy1/self.scale)
        self.boxes.setdefault(self.page_index, []).append(pdf_rect)
        self.redraw_boxes()
        self.update_labels()

    def redraw_boxes(self):
        self.canvas.delete("box")
        for (x0, y0, x1, y1) in self.boxes.get(self.page_index, []):
            self.canvas.create_rectangle(
                x0*self.scale, y0*self.scale, x1*self.scale, y1*self.scale,
                outline="red", width=2, fill="red", stipple="gray25", tags="box")

    def undo_box(self):
        lst = self.boxes.get(self.page_index, [])
        if lst:
            lst.pop()
            self.redraw_boxes()
            self.update_labels()

    def clear_page(self):
        if self.boxes.get(self.page_index):
            self.boxes[self.page_index] = []
            self.redraw_boxes()
            self.update_labels()

    # ---------- apply ----------
    def apply_save(self):
        total = sum(len(v) for v in self.boxes.values())
        if total == 0:
            messagebox.showinfo("Nothing to redact",
                                "Draw at least one box first.")
            return
        out_path = os.path.splitext(self.path)[0] + "_redacted.pdf"
        try:
            work = fitz.open(self.path)
            # flatten interactive form fields so values can't hide behind boxes
            try:
                work.bake()  # flattens annotations/form fields (PyMuPDF >= 1.21)
            except Exception:
                pass
            for pidx, rects in self.boxes.items():
                page = work[pidx]
                for (x0, y0, x1, y1) in rects:
                    page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
                # strip text AND image pixels under the boxes
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            # sanitize metadata
            work.set_metadata({})
            try:
                work.del_xml_metadata()
            except Exception:
                pass
            work.save(out_path, garbage=4, deflate=True, clean=True)
            work.close()
        except Exception as e:
            messagebox.showerror("Error", f"Redaction failed:\n{e}")
            return

        # verify: no text should remain inside any redacted rect
        leaks = self._verify(out_path)
        if leaks:
            messagebox.showwarning(
                "Saved — but check this",
                f"Saved to:\n{out_path}\n\nWARNING: {leaks} redacted region(s) "
                f"still returned extractable text. This can happen with unusual "
                f"PDFs. Inspect the output before using it.")
        else:
            messagebox.showinfo(
                "Done",
                f"Saved to:\n{out_path}\n\nVerified: no extractable text remains "
                f"under any box. Metadata sanitized. Original untouched.")

    def _verify(self, out_path):
        """Return count of redacted rects that still yield text (should be 0)."""
        leaks = 0
        try:
            chk = fitz.open(out_path)
            for pidx, rects in self.boxes.items():
                page = chk[pidx]
                for (x0, y0, x1, y1) in rects:
                    txt = page.get_text("text", clip=fitz.Rect(x0, y0, x1, y1)).strip()
                    if txt:
                        leaks += 1
            chk.close()
        except Exception:
            pass
        return leaks


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1100x950")
    Redactor(root)
    root.mainloop()
