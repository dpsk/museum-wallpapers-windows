"""The "About this painting" card: a small dark window above the tray with a
preview, the title, artist, museum, the story, and Next / Read more / Save /
More by … buttons. Tk runs on its own thread; show() and close() may be
called from any thread."""

import gc
import queue
import sys
import threading
import traceback

DARK = "#1c1b19"
PANEL = "#26241f"
TEXT = "#f2eee6"
SECONDARY = "#c9c1b3"
DIM = "#968e80"
ACCENT = "#c99e48"
ACCENT_HOVER = "#e0b865"
BUTTON = "#34312b"
BUTTON_HOVER = "#45413a"
ERROR = "#e39a7a"

WIDTH = 420  # at 100% scaling
PREVIEW_MAX_HEIGHT = 250
SUMMARY_LIMIT = 700


def shorten(text, limit):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


class Card:
    """`actions` maps names (next, open, save, more_by, more_of, show_all) to
    callables; `work_area` returns (left, top, right, bottom) of the screen
    area above the taskbar in physical pixels, or None."""

    def __init__(self, actions, work_area=None):
        self.actions = actions
        self.work_area = work_area
        self._queue = queue.Queue()
        self._thread = None
        self._window = None
        self._images = []
        self._ready = threading.Event()
        self._last = None
        self._close_on_blur = True
        self.available = True

    # -- thread-safe API

    def show(self, data):
        """Open the card (or refresh it in place) with `data` from App.card_data()."""
        self._start()
        self._queue.put(("show", data))

    def update(self, data):
        """Refresh the card if it is open."""
        if self._thread:
            self._queue.put(("update", data))

    def busy(self, text):
        if self._thread:
            self._queue.put(("busy", text))

    def close(self):
        if self._thread:
            self._queue.put(("close", None))

    def quit(self, timeout=2):
        """Stop the Tk thread and wait for it to tear Tk down."""
        if self._thread:
            self._queue.put(("quit", None))
            self._thread.join(timeout)

    @property
    def is_open(self):
        return self._window is not None

    # -- Tk thread

    def _start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="card", daemon=True)
            self._thread.start()
            self._ready.wait(10)

    def _loop(self):
        try:
            import tkinter as tk
            from tkinter import font as tkfont
        except ImportError:
            self.available = False
            self._ready.set()
            return
        self.tk, self.tkfont = tk, tkfont
        self.root = tk.Tk()
        self.root.withdraw()
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        families = set(tkfont.families(self.root))
        serif = next((f for f in ("Georgia", "Cambria", "DejaVu Serif") if f in families), "Times")
        sans = next((f for f in ("Segoe UI", "Segoe UI Variable Text", "DejaVu Sans") if f in families), "Helvetica")
        self.fonts = {
            "title": (serif, 15, "italic"),
            "byline": (sans, 10),
            "small": (sans, 9),
            "body": (sans, 10),
            "button": (sans, 10),
            "link": (sans, 9, "underline"),
        }
        self._ready.set()
        self.root.after(50, self._poll)
        try:
            self.root.mainloop()
        finally:
            # Tcl objects must die on the thread that made them, never in
            # the main thread's garbage collection at exit (a Tcl panic).
            self._close()
            try:
                self.root.destroy()
            except Exception:  # noqa: BLE001
                pass
            self.root = self._window = self._status = None
            self._images = []
            self._last = None
            gc.collect()

    def _poll(self):
        """Run queued commands; one failing never stops the card for good."""
        try:
            while True:
                command, data = self._queue.get_nowait()
                try:
                    if command == "quit":
                        self._close()
                        self.root.quit()
                        return
                    self._command(command, data)
                except Exception:  # noqa: BLE001
                    print("museum-wallpapers: card: " + traceback.format_exc(), file=sys.stderr)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _command(self, command, data):
        if command == "show":
            self._render(data, focus=True)
        elif command == "update" and self._window is not None and data != self._last:
            self._render(data, focus=False)
        elif command == "busy" and self._window is not None:
            self._status.configure(text=data, fg=SECONDARY)
        elif command == "close":
            self._close()

    def _px(self, value):
        return int(value * self.scale)

    def _close(self, _event=None):
        if self._window is not None:
            self._window.destroy()
            self._window = None
            self._images = []
            self._last = None

    def _button(self, parent, text, action, primary=False):
        tk = self.tk
        bg, hover = (ACCENT, ACCENT_HOVER) if primary else (BUTTON, BUTTON_HOVER)
        fg = DARK if primary else TEXT
        button = tk.Label(parent, text=text, bg=bg, fg=fg, font=self.fonts["button"], cursor="hand2",
                          padx=self._px(12), pady=self._px(6))
        button.bind("<Enter>", lambda _e: button.configure(bg=hover))
        button.bind("<Leave>", lambda _e: button.configure(bg=bg))
        button.bind("<Button-1>", lambda _e: self._run(action))
        return button

    def _link(self, parent, text, action):
        tk = self.tk
        link = tk.Label(parent, text=text, bg=DARK, fg=ACCENT, font=self.fonts["link"], cursor="hand2")
        link.bind("<Enter>", lambda _e: link.configure(fg=ACCENT_HOVER))
        link.bind("<Leave>", lambda _e: link.configure(fg=ACCENT))
        link.bind("<Button-1>", lambda _e: self._run(action))
        return link

    def _run(self, action):
        callback = self.actions.get(action[0]) if isinstance(action, tuple) else self.actions.get(action)
        if not callback:
            return
        args = action[1:] if isinstance(action, tuple) else ()
        threading.Thread(target=callback, args=args, daemon=True).start()

    def _preview(self, path, width):
        try:
            from PIL import Image, ImageOps, ImageTk
            with Image.open(path) as image:
                image.draft("RGB", (width, width))
                image = ImageOps.contain(image.convert("RGB"), (width, self._px(PREVIEW_MAX_HEIGHT)),
                                         Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image, master=self.root)
            self._images.append(photo)
            return photo
        except Exception:  # noqa: BLE001 - no preview rather than no card
            return None

    def _on_focus_out(self, event):
        window = self._window
        if window is None or event.widget is not window or not self._close_on_blur:
            return
        # FocusOut also fires when focus moves to a child; close only when
        # it left the card (checked once Tk has settled the new focus).
        def check():
            if self._window is window and window.focus_get() is None:
                self._close()
        window.after(150, check)

    def _render(self, data, focus):
        tk = self.tk
        self._last = data
        self._close_on_blur = data.get("closeOnBlur", True)
        old_position = None
        if self._window is not None:
            # Same window: it keeps its focus (so a click elsewhere still
            # closes it) and its place, growing or shrinking upwards like a
            # tray flyout.
            window = self._window
            old_position = (window.winfo_x(), window.winfo_y() + window.winfo_height())
            for child in window.winfo_children():
                child.destroy()
            self._images = []
        else:
            window = tk.Toplevel(self.root, bg=DARK, highlightthickness=1, highlightbackground="#3d3a33")
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.bind("<Escape>", self._close)
            window.bind("<FocusOut>", self._on_focus_out)
            self._window = window
        pad, width = self._px(16), self._px(WIDTH)
        inner = width - 2 * pad
        wrap = inner - self._px(6)
        labels = data["labels"]

        top = tk.Frame(window, bg=DARK)
        top.pack(fill="x", padx=pad, pady=(self._px(10), 0))
        tk.Label(top, text=labels["app"], bg=DARK, fg=DIM, font=self.fonts["small"]).pack(side="left")
        close = tk.Label(top, text="✕", bg=DARK, fg=DIM, font=self.fonts["byline"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", self._close)

        info = data.get("info")
        if data.get("preview"):
            photo = self._preview(data["preview"], inner)
            if photo:
                tk.Label(window, image=photo, bg=DARK, cursor="hand2").pack(padx=pad, pady=(self._px(8), 0))

        body = tk.Frame(window, bg=DARK)
        body.pack(fill="x", padx=pad, pady=(self._px(10), 0))
        if info:
            title = tk.Label(body, text=info["title"], bg=DARK, fg=TEXT, font=self.fonts["title"], justify="left",
                             anchor="w", wraplength=wrap)
            title.pack(fill="x")
            for text, font, color in ((data.get("byline"), "byline", SECONDARY),
                                      (data.get("place"), "small", DIM)):
                if text:
                    tk.Label(body, text=text, bg=DARK, fg=color, font=self.fonts[font], justify="left", anchor="w",
                             wraplength=wrap).pack(fill="x", pady=(self._px(2), 0))
            if info.get("summary"):
                tk.Label(body, text=shorten(info["summary"], SUMMARY_LIMIT), bg=DARK, fg=TEXT,
                         font=self.fonts["body"], justify="left", anchor="w",
                         wraplength=wrap).pack(fill="x", pady=(self._px(10), 0))
        else:
            tk.Label(body, text=labels["no_painting"], bg=DARK, fg=SECONDARY, font=self.fonts["body"],
                     justify="left", anchor="w", wraplength=wrap).pack(fill="x")

        if data.get("filter"):
            row = tk.Frame(window, bg=DARK)
            row.pack(fill="x", padx=pad, pady=(self._px(10), 0))
            tk.Label(row, text=data["filter"], bg=DARK, fg=SECONDARY, font=self.fonts["small"]).pack(side="left")
            self._link(row, labels["show_all"], "show_all").pack(side="left", padx=(self._px(8), 0))

        buttons = tk.Frame(window, bg=DARK)
        buttons.pack(fill="x", padx=pad, pady=(self._px(14), 0))
        self._button(buttons, labels["next"], "next", primary=True).pack(side="left")
        if info:
            self._button(buttons, labels["read_more"], "open").pack(side="left", padx=(self._px(8), 0))
            self._button(buttons, labels["save_short"], "save").pack(side="left", padx=(self._px(8), 0))

        more = [(text, action) for text, action in data.get("more", []) if text]
        if more:
            row = tk.Frame(window, bg=DARK)
            row.pack(fill="x", padx=pad, pady=(self._px(10), 0))
            for n, (text, action) in enumerate(more):
                self._link(row, text, action).pack(side="left", padx=(0 if n == 0 else self._px(14), 0))

        self._status = tk.Label(window, text=data.get("error") or "", bg=DARK, fg=ERROR, font=self.fonts["small"],
                                justify="left", anchor="w", wraplength=wrap)
        self._status.pack(fill="x", padx=pad, pady=(self._px(8), self._px(12)))

        window.update_idletasks()
        height = window.winfo_reqheight()
        if old_position:
            area = self._area()
            x, bottom = old_position
            y = min(bottom, area[3] - self._px(12)) - height
        else:
            area = self._area()
            x, y = area[2] - width - self._px(12), area[3] - height - self._px(12)
        window.geometry(f"{width}x{height}+{max(area[0], x)}+{max(area[1], y)}")
        if focus:
            window.lift()
            window.focus_force()

    def _area(self):
        if self.work_area:
            try:
                area = self.work_area()
                if area:
                    return area
            except Exception:  # noqa: BLE001
                pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight() - self._px(48))
