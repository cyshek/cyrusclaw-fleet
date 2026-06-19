"""
Discreet always-on-top overlay for suggestions.

Real-world hardening (noted, not all implementable on Linux/headless):
  - Windows: SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE) -> invisible
    to screen-share / OBS while still visible to you.
  - macOS: NSWindow.sharingType = .none -> excluded from screen capture.
  - Click-through: WS_EX_TRANSPARENT (Win) / ignoresMouseEvents (mac).
This tkinter version is the cross-platform visual stand-in.
"""

from __future__ import annotations
import threading
import queue


class Overlay:
    def __init__(self):
        self._q = queue.Queue()
        self._thread = None
        self._root = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        import tkinter as tk
        self._root = tk.Tk()
        self._root.title("copilot")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.92)
        self._root.overrideredirect(True)
        self._root.geometry("420x120+40+40")
        self._root.configure(bg="#11141a")
        self._label = tk.Label(
            self._root, text="listening…", justify="left", anchor="nw",
            wraplength=400, fg="#e6edf3", bg="#11141a",
            font=("Helvetica", 12), padx=12, pady=10,
        )
        self._label.pack(fill="both", expand=True)
        self._poll()
        self._root.mainloop()

    def _poll(self):
        try:
            while True:
                kind, text, lat = self._q.get_nowait()
                self._label.config(text=f"[{kind}] {lat}ms\n\n{text}")
        except queue.Empty:
            pass
        if self._root:
            self._root.after(120, self._poll)

    def show(self, suggestion):
        self._q.put((suggestion.kind, suggestion.text, suggestion.latency_ms))

    def stop(self):
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass
