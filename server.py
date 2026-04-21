#!/usr/bin/env python3
"""
RoArm-M2-S Mission Manager — UART bridge server
Run: python server.py --port COM3   (Windows)
     python server.py --port /dev/ttyUSB0   (Linux/Mac)
Then open http://localhost:5000 in your browser.
"""

import argparse
import json
import re
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

try:
    import serial
except ImportError:
    print("pyserial not found. Install it with:  pip install pyserial")
    raise

BAUD = 115200
SCRIPT_DIR = Path(__file__).parent
UI_FILE = SCRIPT_DIR / "index.html"

ser: "serial.Serial | None" = None
ser_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Serial helpers
# ---------------------------------------------------------------------------


def send_cmd(cmd: dict, timeout: float = 5.0) -> str:
    """Send a JSON command and return the raw response string.

    Reads until the port has been silent for IDLE_S seconds,
    or until `timeout` seconds have elapsed overall.
    """
    assert ser is not None, "Serial port not open"
    IDLE_S = 0.15  # stop after 150 ms of silence
    with ser_lock:
        ser.reset_input_buffer()
        raw_cmd = json.dumps(cmd, separators=(",", ":")) + "\n"
        ser.write(raw_cmd.encode())
        print(f"  >> {raw_cmd.strip()}")

        deadline = time.time() + timeout
        buf = b""
        last_data = time.time()

        while time.time() < deadline:
            waiting = ser.in_waiting
            if waiting:
                chunk = ser.read(waiting)
                buf += chunk
                last_data = time.time()
            else:
                # Stop once we have seen some data and line has gone quiet
                if buf and (time.time() - last_data) >= IDLE_S:
                    break
                time.sleep(0.02)

        result = buf.decode(errors="replace").strip()
        suffix = "..." if len(result) > 300 else ""
        print(f"  << {repr(result[:300])}{suffix}")
        return result


def read_file_lines(name: str) -> list[str]:
    """Read a mission file using T:221 (CMD_MISSION_CONTENT).

    No .mission suffix needed in the name for mission commands.
    Response format:
      {"name":"...","intro":"..."}        <- bare header JSON (first line)
      [StepNum: 1 ] - {"T":104,...}       <- step lines
      [StepNum: 2 ] - {"T":114,...}

    Returns all lines (header first, then steps) so the caller can
    strip the header out and display it separately.
    """
    resp = send_cmd({"T": 221, "name": name}, timeout=6.0)
    lines = []
    for raw in resp.splitlines():
        raw = raw.strip()
        # Step lines
        if raw.startswith("[StepNum:"):
            m = re.search(r"-\s*(\{.*\})\s*$", raw)
            if m:
                lines.append(m.group(1))
        # Header line — bare JSON object that has "name" but no "T" key
        elif raw.startswith("{") and raw.endswith("}"):
            try:
                obj = json.loads(raw)
                if "name" in obj and "T" not in obj:
                    lines.insert(0, raw)  # always first
            except Exception:
                pass
    return lines


def list_missions() -> list[dict]:
    """Scan flash and return list of {name, intro} dicts.

    Real arm output (each token on its own line):
        [file]: [boot.mission]
        [first line]:
        {"name":"boot","intro":"..."}
    """
    resp = send_cmd({"T": 200}, timeout=6.0)
    missions = []

    lines = resp.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        fm = re.match(r"\[file\]:\s*\[(.+?)\]", line)
        if fm:
            fname = fm.group(1).strip()
            if fname.endswith(".mission"):
                mission_name = fname[:-8]
                intro = ""
                # Scan ahead up to 5 lines for the JSON after [first line]:
                for j in range(i + 1, min(i + 6, len(lines))):
                    candidate = lines[j].strip()
                    if candidate.startswith("{"):
                        try:
                            intro = json.loads(candidate).get("intro", "")
                        except Exception:
                            pass
                        break
                missions.append({"name": mission_name, "intro": intro})
        i += 1

    return missions


def save_mission(name: str, intro: str, steps: list[str]) -> dict:
    """Recreate a mission and populate it with steps.

    Command reference (no .mission suffix for mission commands):
      T:220  CMD_CREATE_MISSION  — creates/overwrites the mission file
      T:222  CMD_APPEND_STEP_JSON — appends one step

    T:222 step format per wiki:
      {"T":222,"name":"mission_a","step":"{\"T\":104,\"x\":235,...}"}
    The step value is a compact JSON string; json.dumps on the outer dict
    escapes the inner quotes automatically.
    """
    errors = []

    # T:220 does NOT overwrite — it fails silently if the file exists.
    # Delete first with T:203 (requires .mission suffix), then recreate.
    send_cmd({"T": 203, "name": f"{name}.mission"})
    time.sleep(0.2)
    send_cmd({"T": 220, "name": name, "intro": intro})
    time.sleep(0.2)

    for i, step in enumerate(steps):
        step = step.strip()
        if not step:
            continue
        try:
            step_str = json.dumps(json.loads(step), separators=(",", ":"))
        except json.JSONDecodeError as e:
            errors.append(f"Step {i + 1} invalid JSON: {e}")
            continue
        send_cmd({"T": 222, "name": name, "step": step_str})
        time.sleep(0.15)

    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "steps_saved": len(steps)}


def delete_mission(name: str) -> dict:
    """Delete a mission file using T:203 (CMD_DELETE_FILE).

    T:203 is the FLASH file system delete command and requires the
    full filename including the .mission suffix.
    """
    send_cmd({"T": 203, "name": f"{name}.mission"})
    time.sleep(0.2)
    return {"ok": True}


def run_mission(name: str, times: int = 1) -> dict:
    """Play a mission using T:242 (CMD_MISSION_PLAY).

    name: mission name without .mission suffix.
    times: number of loops (-1 = infinite).
    """
    send_cmd({"T": 242, "name": name, "times": times}, timeout=2.0)
    return {"ok": True}


def run_step(name: str, step_num: int) -> dict:
    """Execute a single step using T:241 (CMD_MOVE_TO_STEP).

    name: mission name without .mission suffix.
    step_num: 1-based step number to execute.
    Note: may block on the serial side if the step involves
    blocking motion commands — the 10s timeout is intentional.
    """
    send_cmd({"T": 241, "name": name, "stepNum": step_num}, timeout=10.0)
    return {"ok": True}


def stop_mission() -> dict:
    """Stop mission playback.

    Per the wiki, any serial signal causes playback to exit after the
    current step completes. We send a no-op T:0 to trigger this.
    """
    send_cmd({"T": 0}, timeout=2.0)
    return {"ok": True}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        print(f"  {self.address_string()} {format % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, path: Path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/"):
            if UI_FILE.exists():
                self.send_html(UI_FILE)
            else:
                self.send_json({"error": "index.html not found next to server.py"}, 404)

        elif path == "/api/missions":
            try:
                self.send_json(list_missions())
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path.startswith("/api/missions/"):
            name = path[len("/api/missions/") :]
            try:
                lines = read_file_lines(name)
                self.send_json({"name": name, "lines": lines})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if path.startswith("/api/missions/"):
            name = path[len("/api/missions/") :]
            intro = body.get("intro", "")
            steps = body.get("steps", [])
            try:
                result = save_mission(name, intro, steps)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        elif path.startswith("/api/run/mission/"):
            name = path[len("/api/run/mission/") :]
            times = body.get("times", 1)
            try:
                self.send_json(run_mission(name, times))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path == "/api/run/stop":
            try:
                self.send_json(stop_mission())
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif path.startswith("/api/run/step/"):
            name = path[len("/api/run/step/") :]
            step_num = body.get("stepNum")
            if step_num is None:
                self.send_json({"error": "stepNum required"}, 400)
                return
            try:
                self.send_json(run_step(name, int(step_num)))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        else:
            self.send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/api/missions/"):
            name = path[len("/api/missions/") :]
            try:
                self.send_json(delete_mission(name))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"error": "not found"}, 404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="RoArm-M2-S Mission Manager bridge")
    parser.add_argument(
        "--port", default="/dev/ttyUSB0", help="Serial port (e.g. COM3 or /dev/ttyUSB0)"
    )
    parser.add_argument("--baud", type=int, default=BAUD)
    parser.add_argument("--http-port", type=int, default=5000)
    args = parser.parse_args()

    global ser
    print(f"Opening serial port {args.port} at {args.baud} baud...")
    ser = serial.Serial(args.port, args.baud, timeout=1)
    time.sleep(2)
    print(f"Serial OK. Starting HTTP server on http://localhost:{args.http_port}")
    print("Open that URL in your browser.\n")

    server = HTTPServer(("localhost", args.http_port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
