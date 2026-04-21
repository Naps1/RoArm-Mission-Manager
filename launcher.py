"""
RoArm Mission Manager - GUI Launcher
Works on Windows, Linux and macOS.
Build a standalone Windows exe with:  pyinstaller RoArmManager.spec
"""

import sys
import os
import platform
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import queue
from typing import Any, cast

# ── Locate bundled files ───────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = cast(str, getattr(sys, "_MEIPASS"))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
PYTHON_EXE = sys.executable

HTTP_PORT = 5000

# ── Colours ────────────────────────────────────────────────────────────────────
BG = "#1a1e25"
BG2 = "#13161b"
BG3 = "#252a33"
ACC = "#4af0a0"
TXT = "#c9d1db"
TXT2 = "#7a8694"
TXT3 = "#3f4855"
BORD = "#30363f"

# ── Cross-platform fonts ───────────────────────────────────────────────────────
_OS = platform.system()
if _OS == "Windows":
    FONT_UI = ("Segoe UI", 10)
    FONT_MONO = ("Consolas", 9)
    FONT_HEAD = ("Segoe UI", 13, "bold")
    FONT_SM = ("Segoe UI", 9)
elif _OS == "Darwin":
    FONT_UI = ("SF Pro Text", 10)
    FONT_MONO = ("Menlo", 9)
    FONT_HEAD = ("SF Pro Display", 13, "bold")
    FONT_SM = ("SF Pro Text", 9)
else:
    FONT_UI = ("DejaVu Sans", 10)
    FONT_MONO = ("DejaVu Sans Mono", 9)
    FONT_HEAD = ("DejaVu Sans", 13, "bold")
    FONT_SM = ("DejaVu Sans", 9)

# ── Serial port detection ──────────────────────────────────────────────────────
KNOWN_VIDS = {
    (0x10C4, 0xEA60): "CP210x",
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x0403, 0x6001): "FTDI",
    (0x303A, 0x1001): "ESP32-USB",
}


def list_ports():
    """Return list of (device, label, is_known) sorted known-first."""
    try:
        from serial.tools.list_ports import comports

        ports = comports()
    except ImportError:
        return []
    result = []
    for p in ports:
        chip = KNOWN_VIDS.get((p.vid, p.pid)) if p.vid and p.pid else None
        label = f"{p.device}  -  {chip or p.description or 'Unknown'}"
        result.append((p.device, label, bool(chip)))
    result.sort(key=lambda x: (not x[2], x[0]))
    return result


# ── Main application window ────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RoArm Mission Manager")
        self.resizable(True, True)
        self.geometry("680x520")
        self.configure(bg=BG)

        self._server_proc: subprocess.Popen[str] | None = None
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._running = False
        self._browser_btn_enabled_cfg: dict[str, Any] = {}
        self._browser_btn_disabled_cfg: dict[str, Any] = {}

        self._build_ui()
        self._refresh_ports()
        self._poll_log()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        PAD = 16

        # Header
        hdr = tk.Frame(self, bg=BG2, padx=PAD, pady=10)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="RoArm Mission Manager", font=FONT_HEAD, fg=ACC, bg=BG2
        ).pack(side="left")
        self._status_dot = tk.Label(hdr, text="  ", bg=TXT3, relief="flat", width=2)
        self._status_dot.pack(side="right", padx=(0, 4))
        self._status_lbl = tk.Label(hdr, text="stopped", font=FONT_SM, fg=TXT2, bg=BG2)
        self._status_lbl.pack(side="right", padx=(0, 6))

        # Port row
        port_frame = tk.Frame(self, bg=BG, padx=PAD, pady=12)
        port_frame.pack(fill="x")

        tk.Label(port_frame, text="Serial port", font=FONT_UI, fg=TXT2, bg=BG).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=BG3,
            background=BG3,
            foreground=TXT,
            selectbackground=BG3,
            selectforeground=TXT,
            bordercolor=BORD,
            arrowcolor=TXT2,
        )
        self._port_var = tk.StringVar()
        self._port_combo = ttk.Combobox(
            port_frame,
            textvariable=self._port_var,
            state="readonly",
            width=36,
            style="Dark.TCombobox",
            font=FONT_MONO,
        )
        self._port_combo.grid(row=0, column=1, padx=(0, 8))

        tk.Button(
            port_frame,
            text="Refresh",
            font=FONT_SM,
            fg=TXT2,
            bg=BG3,
            activeforeground=ACC,
            activebackground=BG3,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=4,
            command=self._refresh_ports,
        ).grid(row=0, column=2)

        # Action buttons
        btn_frame = tk.Frame(self, bg=BG, padx=PAD, pady=4)
        btn_frame.pack(fill="x")
        btn_cfg: dict[str, Any] = dict(
            font=FONT_UI, relief="flat", bd=0, cursor="hand2", padx=18, pady=8
        )

        self._start_btn = tk.Button(
            btn_frame,
            text="Start server",
            fg="#0d0f12",
            bg=ACC,
            activebackground="#2dd882",
            activeforeground="#0d0f12",
            command=self._start_server,
            **btn_cfg,
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = tk.Button(
            btn_frame,
            text="Stop server",
            fg=TXT,
            bg=BG3,
            activebackground=BORD,
            activeforeground=TXT,
            state="disabled",
            command=self._stop_server,
            **btn_cfg,
        )
        self._stop_btn.pack(side="left", padx=(0, 8))

        self._browser_btn = tk.Button(
            btn_frame,
            text="Open browser",
            fg=TXT2,
            bg=BG,
            activebackground=BG3,
            activeforeground=TXT,
            state="disabled",
            command=self._open_browser,
            **btn_cfg,
        )
        self._browser_btn_enabled_cfg = dict(fg=TXT, bg=BG3)
        self._browser_btn_disabled_cfg = dict(fg=TXT2, bg=BG)
        self._browser_btn.pack(side="right")

        # Log area
        log_outer = tk.Frame(self, bg=BG, padx=PAD)
        log_outer.pack(fill="both", expand=True, pady=(4, PAD))
        tk.Label(log_outer, text="Server log", font=FONT_SM, fg=TXT2, bg=BG).pack(
            anchor="w", pady=(0, 4)
        )

        self._log = scrolledtext.ScrolledText(
            log_outer,
            width=62,
            height=14,
            font=FONT_MONO,
            bg=BG2,
            fg=TXT,
            insertbackground=TXT,
            selectbackground=BG3,
            relief="flat",
            bd=0,
            state="disabled",
        )
        self._log.pack(fill="both", expand=True)
        self._log.tag_config("ok", foreground=ACC)
        self._log.tag_config("err", foreground="#f05a4a")
        self._log.tag_config("cmd", foreground=TXT2)

        self.update_idletasks()
        self.minsize(420, 400)

    # ── Ports ──────────────────────────────────────────────────────────────────
    def _refresh_ports(self):
        ports = list_ports()
        if ports:
            self._port_labels = [label for _, label, _ in ports]
            self._port_devices = [dev for dev, _, _ in ports]
        else:
            self._port_labels = ["No serial ports found"]
            self._port_devices = []
        self._port_combo["values"] = self._port_labels
        self._port_combo.current(0)

    def _selected_port(self):
        idx = self._port_combo.current()
        if 0 <= idx < len(self._port_devices):
            return self._port_devices[idx]
        return None

    # ── Server lifecycle ───────────────────────────────────────────────────────
    def _start_server(self):
        port = self._selected_port()
        if not port:
            messagebox.showerror(
                "No port selected",
                "Please select a serial port.\n"
                "Make sure the arm is plugged in and click Refresh.",
            )
            return

        self._set_status("starting...", "#f0a94a")
        self._start_btn.config(state="disabled")
        self._log_write(f"Starting server on {port}...\n", "ok")

        cmd = [PYTHON_EXE, SERVER_SCRIPT, "--port", port, "--http-port", str(HTTP_PORT)]
        extra = (
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if sys.platform == "win32"
            else {}
        )
        try:
            self._server_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **extra,
            )
        except Exception as e:
            self._log_write(f"Failed to start: {e}\n", "err")
            self._set_status("error", "#f05a4a")
            self._start_btn.config(state="normal")
            return

        self._running = True
        self._set_status("running", ACC)
        self._log_write(f"Server running at http://localhost:{HTTP_PORT}\n", "ok")
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._browser_btn.config(state="normal", **self._browser_btn_enabled_cfg)
        threading.Thread(target=self._read_output, daemon=True).start()

    def _stop_server(self):
        if self._server_proc and self._server_proc.poll() is None:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
        self._server_proc = None
        self._running = False
        self._set_status("stopped", TXT3)
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._browser_btn.config(state="disabled", **self._browser_btn_disabled_cfg)
        self._log_write("Server stopped.\n", "err")

    def _read_output(self):
        try:
            if self._server_proc is None or self._server_proc.stdout is None:
                return
            for line in self._server_proc.stdout:
                self._log_queue.put(line)
        except Exception:
            pass
        if self._running:
            self._log_queue.put("__SERVER_EXITED__\n")

    def _poll_log(self):
        try:
            while True:
                line = self._log_queue.get_nowait()
                if "__SERVER_EXITED__" in line:
                    if self._running:
                        self._stop_server()
                        self._log_write("Server exited unexpectedly.\n", "err")
                else:
                    if line.startswith("  >>") or line.startswith("  <<"):
                        tag = "cmd"
                    elif "error" in line.lower() or "fail" in line.lower():
                        tag = "err"
                    elif "ok" in line.lower():
                        tag = "ok"
                    else:
                        tag = None
                    self._log_write(line, tag)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _set_status(self, text, colour):
        self._status_dot.config(bg=colour)
        self._status_lbl.config(text=text)

    def _log_write(self, text, tag=None):
        self._log.config(state="normal")
        self._log.insert("end", text, tag or "")
        self._log.see("end")
        self._log.config(state="disabled")

    def _open_browser(self):
        webbrowser.open(f"http://localhost:{HTTP_PORT}")

    def _on_close(self):
        if self._running:
            if messagebox.askokcancel(
                "Quit", "The server is still running.\nStop it and quit?"
            ):
                self._stop_server()
                self.destroy()
        else:
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
