"""
Default built-in tools for the agent harness.
Modeled after Claude Code and Antigravity best practices for file operations,
process execution, project management, and workspace coordination.
"""
import sys
import os
import io
import re
import contextlib
import math
import subprocess
import threading
import atexit
import time
import uuid
import collections
import shutil
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from harness.registry import tool
from harness.session import canonical_path, register_project

# Workspace Management State
WORKSPACE_LOCK = threading.RLock()
ACTIVE_WORKSPACE: str = canonical_path(os.getcwd())
_WORKSPACE_LISTENERS: List[Callable[[str], None]] = []

def add_workspace_listener(callback: Callable[[str], None]) -> None:
    """Registers a listener to be notified when the workspace directory changes."""
    with WORKSPACE_LOCK:
        if callback not in _WORKSPACE_LISTENERS:
            _WORKSPACE_LISTENERS.append(callback)

def remove_workspace_listener(callback: Callable[[str], None]) -> None:
    with WORKSPACE_LOCK:
        if callback in _WORKSPACE_LISTENERS:
            _WORKSPACE_LISTENERS.remove(callback)

def get_active_workspace() -> str:
    """Returns the current canonical active workspace path."""
    with WORKSPACE_LOCK:
        return ACTIVE_WORKSPACE

def set_active_workspace(path: str) -> str:
    """Sets active workspace path, updates os.chdir, registers project, and notifies listeners."""
    global ACTIVE_WORKSPACE
    target = canonical_path(path)
    os.makedirs(target, exist_ok=True)
    with WORKSPACE_LOCK:
        ACTIVE_WORKSPACE = target
        try:
            os.chdir(target)
        except Exception:
            pass
        listeners = list(_WORKSPACE_LISTENERS)

    # Register in project storage
    try:
        register_project(target)
    except Exception:
        pass

    # Notify listeners outside lock
    for cb in listeners:
        try:
            cb(target)
        except Exception:
            pass

    return target

def resolve_path(filepath: str, base_dir: Optional[str] = None) -> str:
    """
    Safely resolves any filepath passed by the user or LLM.
    - Strips surrounding quotes, whitespace, and markdown links [text](path).
    - Decodes URL encodings (e.g. %20 -> space).
    - Strips file:/// or file:// URIs.
    - Expands ~ and environment variables.
    - Resolves relative paths against the active workspace.
    - Returns a canonical absolute path.
    """
    if not filepath or not str(filepath).strip():
        return get_active_workspace()

    clean = str(filepath).strip().strip("'\"`")
    # Handle markdown links like [main.py](file:///C:/Users/...) or [main.py](main.py)
    if clean.startswith("[") and "](" in clean and clean.endswith(")"):
        clean = clean[clean.index("](") + 2 : -1].strip()

    # URL decode (%20 -> space, etc.)
    import urllib.parse
    clean = urllib.parse.unquote(clean)

    # Handle file:// URIs
    if clean.lower().startswith("file:///"):
        clean = clean[8:]
    elif clean.lower().startswith("file://"):
        clean = clean[7:]

    # On Windows, path like /C:/Users/... -> C:/Users/...
    if os.name == "nt" and len(clean) >= 3 and clean[0] in ("/", "\\") and clean[2] == ":":
        clean = clean[1:]

    expanded = os.path.expandvars(os.path.expanduser(clean))

    base = base_dir or get_active_workspace()
    if not os.path.isabs(expanded):
        full_path = os.path.join(base, expanded)
    else:
        full_path = expanded

    return canonical_path(full_path)

# Concurrency & Process Management
CURRENT_RUNNING_PROCESS = None
CURRENT_PROCESS_LOCK = threading.Lock()
BACKGROUND_PROCESSES: Dict[int, Dict[str, Any]] = {}
TERMINATED_PROCESS_OUTPUTS: collections.OrderedDict[int, str] = collections.OrderedDict()
TERMINATED_PROCESS_METADATA: collections.OrderedDict[int, Dict[str, Any]] = collections.OrderedDict()
MAX_TERMINATED_OUTPUTS = 50
BACKGROUND_LOCK = threading.RLock()
_BACKGROUND_LISTENERS: List[Callable[[], None]] = []

def _record_terminated_output(
    pid: int,
    output: str,
    command: str = "",
    started_at: str = "",
    workspace: str = "",
    terminated_by_user: bool = False
) -> None:
    with BACKGROUND_LOCK:
        TERMINATED_PROCESS_OUTPUTS[pid] = output
        TERMINATED_PROCESS_METADATA[pid] = {
            "pid": pid,
            "command": command,
            "started_at": started_at,
            "workspace": workspace,
            "terminated_at": datetime.now().strftime("%H:%M:%S"),
            "terminated_by_user": terminated_by_user,
            "output": output
        }
        while len(TERMINATED_PROCESS_OUTPUTS) > MAX_TERMINATED_OUTPUTS:
            TERMINATED_PROCESS_OUTPUTS.popitem(last=False)
        while len(TERMINATED_PROCESS_METADATA) > MAX_TERMINATED_OUTPUTS:
            TERMINATED_PROCESS_METADATA.popitem(last=False)

def add_background_listener(callback: Callable[[], None]) -> None:
    with BACKGROUND_LOCK:
        if callback not in _BACKGROUND_LISTENERS:
            _BACKGROUND_LISTENERS.append(callback)

def remove_background_listener(callback: Callable[[], None]) -> None:
    with BACKGROUND_LOCK:
        if callback in _BACKGROUND_LISTENERS:
            _BACKGROUND_LISTENERS.remove(callback)

def notify_background_listeners() -> None:
    with BACKGROUND_LOCK:
        listeners = list(_BACKGROUND_LISTENERS)
    for cb in listeners:
        try:
            cb()
        except Exception:
            pass

def _format_uptime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    mins = seconds // 60
    secs = seconds % 60
    if mins < 60:
        return f"{mins}m {secs}s"
    hrs = mins // 60
    rem_mins = mins % 60
    return f"{hrs}h {rem_mins}m"

def get_background_tasks() -> List[Dict[str, Any]]:
    """Returns list of currently active background processes with metadata."""
    with BACKGROUND_LOCK:
        active = []
        changed = False
        for pid, info in list(BACKGROUND_PROCESSES.items()):
            proc = info["process"]
            if proc.poll() is None:
                uptime_sec = max(0, int(time.time() - info.get("start_timestamp", time.time())))
                active.append({
                    "pid": pid,
                    "command": info["command"],
                    "workspace": info.get("workspace", ""),
                    "started_at": info.get("started_at", ""),
                    "uptime_seconds": uptime_sec,
                    "uptime": _format_uptime(uptime_sec),
                    "status": "running"
                })
            else:
                buf = info.get("output_lines")
                lock = info.get("output_lock")
                captured = ""
                if buf:
                    if lock:
                        with lock:
                            captured = "".join(buf)
                    else:
                        captured = "".join(buf)
                _record_terminated_output(
                    pid=pid,
                    output=captured,
                    command=info.get("command", ""),
                    started_at=info.get("started_at", ""),
                    workspace=info.get("workspace", ""),
                    terminated_by_user=False
                )
                del BACKGROUND_PROCESSES[pid]
                changed = True

        if changed:
            threading.Thread(target=notify_background_listeners, daemon=True).start()

        return active

def get_background_task_output(pid: int) -> str:
    """Returns captured output for a background process, including recently terminated tasks."""
    try:
        pid = int(pid)
    except Exception:
        return f"Error: Invalid PID '{pid}'."

    with BACKGROUND_LOCK:
        info = BACKGROUND_PROCESSES.get(pid)
        if info:
            buf = info.get("output_lines")
            lock = info.get("output_lock")
            if not buf:
                return "[No output recorded yet]"
            if lock:
                with lock:
                    lines = list(buf)
            else:
                lines = list(buf)
            return "".join(lines) if lines else "[No output recorded yet]"

        if pid in TERMINATED_PROCESS_OUTPUTS:
            out = TERMINATED_PROCESS_OUTPUTS[pid]
            return (out if out else "[Process produced no output]") + "\n\n[Process terminated]"

        return f"No background process found with PID {pid}."

def set_current_process(proc):
    global CURRENT_RUNNING_PROCESS
    with CURRENT_PROCESS_LOCK:
        CURRENT_RUNNING_PROCESS = proc

def terminate_current_process():
    global CURRENT_RUNNING_PROCESS
    with CURRENT_PROCESS_LOCK:
        if CURRENT_RUNNING_PROCESS is not None:
            try:
                pid = CURRENT_RUNNING_PROCESS.pid
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                else:
                    CURRENT_RUNNING_PROCESS.kill()
            except Exception:
                try:
                    CURRENT_RUNNING_PROCESS.kill()
                except Exception:
                    pass
            finally:
                CURRENT_RUNNING_PROCESS = None

def terminate_all_processes():
    terminate_current_process()
    with BACKGROUND_LOCK:
        for pid, info in list(BACKGROUND_PROCESSES.items()):
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                else:
                    info["process"].kill()
            except Exception:
                pass
        BACKGROUND_PROCESSES.clear()
    notify_background_listeners()

atexit.register(terminate_all_processes)

# =====================================================================
# Execution & Shell Tools
# =====================================================================

@tool
def run_powershell(command: str) -> str:
    """Executes a Windows PowerShell command inside the active project workspace. Note: For dev servers or continuous tasks (e.g. 'python server.py', 'npm run dev'), use 'run_background_process' instead."""
    cmd_lower = command.lower().strip()
    server_keywords = ["http.server", "server.py", "npm run dev", "npm start", "vite", "uvicorn", "flask run", "runserver", "fastapi dev", "next dev"]
    if any(kw in cmd_lower for kw in server_keywords) and "start-process" not in cmd_lower:
        return run_background_process(command)

    proc = None
    ws = get_active_workspace()
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ws
        )
        set_current_process(proc)
        try:
            stdout, stderr = proc.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            terminate_current_process()
            return "Error: PowerShell command timed out after 90 seconds. If this is a server or long-running background task, use 'run_background_process'."
        finally:
            set_current_process(None)

        out = (stdout or "").strip()
        err = (stderr or "").strip()
        if proc.returncode != 0 and err:
            return f"[Exit code {proc.returncode}]\n{err}\n{out}".strip()
        return out if out else "[Command completed with no output]"
    except Exception as e:
        set_current_process(None)
        return f"Error executing PowerShell in '{ws}': {type(e).__name__}: {e}"

@tool
def run_background_process(command: str) -> str:
    """Runs a long-running command, dev server, or continuous background task in the background without blocking the agent. Returns its PID and status immediately."""
    ws = get_active_workspace()
    try:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ws,
            creationflags=flags
        )
        pid = proc.pid

        out_buf = collections.deque(maxlen=300)
        out_lock = threading.Lock()

        def _reader(stream, line_buf, lock):
            try:
                for line in iter(stream.readline, ''):
                    if not line:
                        break
                    # Guard against runaway memory on gigantic single lines
                    if len(line) > 4096:
                        line = line[:4096] + "... [truncated line]\n"
                    with lock:
                        line_buf.append(line)
            except Exception:
                pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        t_out = threading.Thread(target=_reader, args=(proc.stdout, out_buf, out_lock), daemon=True)
        t_err = threading.Thread(target=_reader, args=(proc.stderr, out_buf, out_lock), daemon=True)
        t_out.start()
        t_err.start()

        # Wait 1.5s to verify if it exited immediately (syntax error, port in use, etc.)
        time.sleep(1.5)
        ret = proc.poll()
        if ret is not None:
            time.sleep(0.1)
            with out_lock:
                captured = "".join(out_buf).strip()
            return f"Process exited immediately with code {ret}.\nOutput: {captured}"

        with BACKGROUND_LOCK:
            BACKGROUND_PROCESSES[pid] = {
                "command": command,
                "process": proc,
                "workspace": ws,
                "started_at": datetime.now().strftime("%H:%M:%S"),
                "start_timestamp": time.time(),
                "output_lines": out_buf,
                "output_lock": out_lock
            }

        notify_background_listeners()

        return (
            f"Background process started successfully [PID: {pid}].\n"
            f"Workspace: '{ws}'\n"
            f"Command: '{command}'.\n"
            f"Process is running in background. Do NOT loop or test repeatedly; complete your response now."
        )
    except Exception as e:
        return f"Error starting background process: {e}"

@tool
def list_background_processes() -> str:
    """Lists all active background processes and dev servers started in this workspace."""
    with BACKGROUND_LOCK:
        active = []
        changed = False
        for pid, info in list(BACKGROUND_PROCESSES.items()):
            proc = info["process"]
            if proc.poll() is None:
                uptime_sec = max(0, int(time.time() - info.get("start_timestamp", time.time())))
                active.append(f"- PID {pid}: '{info['command']}' (uptime: {_format_uptime(uptime_sec)}, started {info['started_at']}, cwd: {info.get('workspace', '')})")
            else:
                buf = info.get("output_lines")
                lock = info.get("output_lock")
                captured = ""
                if buf:
                    if lock:
                        with lock:
                            captured = "".join(buf)
                    else:
                        captured = "".join(buf)
                _record_terminated_output(
                    pid=pid,
                    output=captured,
                    command=info.get("command", ""),
                    started_at=info.get("started_at", ""),
                    workspace=info.get("workspace", ""),
                    terminated_by_user=False
                )
                del BACKGROUND_PROCESSES[pid]
                changed = True
        if changed:
            threading.Thread(target=notify_background_listeners, daemon=True).start()

        # Check tasks stopped by user
        user_stopped = []
        for pid, meta in list(TERMINATED_PROCESS_METADATA.items()):
            if meta.get("terminated_by_user"):
                user_stopped.append(f"- PID {pid}: '{meta.get('command', '')}' [STOPPED BY USER at {meta.get('terminated_at', '')}]")

        parts = []
        if active:
            parts.append("Active Running Processes:\n" + "\n".join(active) + "\n\nNote: The processes above are actively running. Do NOT repeatedly poll or verify.")
        else:
            parts.append("No background processes currently running.")

        if user_stopped:
            parts.append("Tasks Stopped by User:\n" + "\n".join(user_stopped) + "\n\nNotice: The user stopped these tasks from the UI. Do NOT restart them unless requested.")

        return "\n\n".join(parts)

@tool
def check_background_process(pid: int = 0) -> str:
    """Checks the live execution status and recent stdout/stderr output of a background task or dev server.
    If pid is 0, checks all known background tasks and reports any that are running or were stopped by the user.
    If the user manually stopped or killed a task via the UI, this tool explicitly informs you that the user turned it off.
    """
    try:
        pid = int(pid)
    except Exception:
        return f"Error: Invalid PID '{pid}'."

    with BACKGROUND_LOCK:
        if pid == 0:
            active_tasks = get_background_tasks()
            lines = []
            if active_tasks:
                lines.append(f"Currently Running Tasks ({len(active_tasks)}):")
                for t in active_tasks:
                    lines.append(f"- PID {t['pid']}: '{t['command']}' (uptime: {t['uptime']}, started: {t['started_at']})")
            else:
                lines.append("No background tasks are currently running.")

            user_stopped = [m for m in TERMINATED_PROCESS_METADATA.values() if m.get("terminated_by_user")]
            if user_stopped:
                lines.append("\nTasks Recently Stopped by User:")
                for m in user_stopped:
                    lines.append(f"- PID {m['pid']}: '{m['command']}' (stopped by user at {m['terminated_at']})")

            return "\n".join(lines)

        info = BACKGROUND_PROCESSES.get(pid)
        if info:
            proc = info["process"]
            if proc.poll() is None:
                uptime_sec = max(0, int(time.time() - info.get("start_timestamp", time.time())))
                buf = info.get("output_lines")
                lock = info.get("output_lock")
                captured = ""
                if buf:
                    if lock:
                        with lock:
                            captured = "".join(buf)
                    else:
                        captured = "".join(buf)

                recent_lines = "\n".join(captured.strip().splitlines()[-15:]) if captured.strip() else "[No output produced yet]"
                return (
                    f"Status: RUNNING (active)\n"
                    f"PID: {pid}\n"
                    f"Command: '{info['command']}'\n"
                    f"Uptime: {_format_uptime(uptime_sec)} (started: {info.get('started_at', '')})\n"
                    f"Workspace: '{info.get('workspace', '')}'\n"
                    f"Recent Output:\n{recent_lines}"
                )
            else:
                buf = info.get("output_lines")
                lock = info.get("output_lock")
                captured = ""
                if buf:
                    if lock:
                        with lock:
                            captured = "".join(buf)
                    else:
                        captured = "".join(buf)
                _record_terminated_output(
                    pid=pid,
                    output=captured,
                    command=info.get("command", ""),
                    started_at=info.get("started_at", ""),
                    workspace=info.get("workspace", ""),
                    terminated_by_user=False
                )
                del BACKGROUND_PROCESSES[pid]
                threading.Thread(target=notify_background_listeners, daemon=True).start()

        meta = TERMINATED_PROCESS_METADATA.get(pid)
        if meta:
            recent_output = "\n".join(meta.get("output", "").strip().splitlines()[-15:]) if meta.get("output") else "[No output]"
            if meta.get("terminated_by_user"):
                return (
                    f"Status: STOPPED BY USER\n"
                    f"PID: {pid}\n"
                    f"Command: '{meta.get('command', '')}'\n"
                    f"Started at: {meta.get('started_at', '')}\n"
                    f"Stopped by user at: {meta.get('terminated_at', '')}\n"
                    f"Notice: The user explicitly turned off / stopped this task from the UI.\n"
                    f"Last output before termination:\n{recent_output}"
                )
            else:
                return (
                    f"Status: TERMINATED / EXITED\n"
                    f"PID: {pid}\n"
                    f"Command: '{meta.get('command', '')}'\n"
                    f"Started at: {meta.get('started_at', '')}\n"
                    f"Terminated at: {meta.get('terminated_at', '')}\n"
                    f"Last output:\n{recent_output}"
                )

        if pid in TERMINATED_PROCESS_OUTPUTS:
            out = TERMINATED_PROCESS_OUTPUTS[pid]
            recent_output = "\n".join(out.strip().splitlines()[-15:]) if out else "[No output]"
            return (
                f"Status: TERMINATED\n"
                f"PID: {pid}\n"
                f"Last output:\n{recent_output}"
            )

        return f"No background task found with PID {pid}."

@tool
def stop_background_process(pid: int, terminated_by_user: bool = False) -> str:
    """Terminates an active background process or dev server by its PID."""
    try:
        pid = int(pid)
    except Exception:
        return f"Error: Invalid PID '{pid}'."

    with BACKGROUND_LOCK:
        info = BACKGROUND_PROCESSES.get(pid)
        if not info:
            if os.name == "nt":
                res = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    _record_terminated_output(
                        pid=pid,
                        output="Process terminated via taskkill.",
                        command=f"PID {pid}",
                        terminated_by_user=terminated_by_user
                    )
                    notify_background_listeners()
                    prefix = "User" if terminated_by_user else "Agent"
                    return f"{prefix} terminated process with PID {pid}."
            return f"No background process found with PID {pid}."
        try:
            buf = info.get("output_lines")
            lock = info.get("output_lock")
            captured = ""
            if buf:
                if lock:
                    with lock:
                        captured = "".join(buf)
                else:
                    captured = "".join(buf)

            cmd_str = info.get("command", "")
            start_str = info.get("started_at", "")
            ws_str = info.get("workspace", "")

            _record_terminated_output(
                pid=pid,
                output=captured,
                command=cmd_str,
                started_at=start_str,
                workspace=ws_str,
                terminated_by_user=terminated_by_user
            )

            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
            else:
                info["process"].kill()
            del BACKGROUND_PROCESSES[pid]
            notify_background_listeners()

            if terminated_by_user:
                return f"Background process [PID: {pid}] ('{cmd_str}') was successfully stopped by user."
            return f"Successfully stopped background process [PID: {pid}]."
        except Exception as e:
            return f"Error stopping process {pid}: {e}"

@tool
def calculate(expression: str) -> str:
    """Evaluates a safe mathematical expression (e.g. '25 * 4 + math.sqrt(144)')."""
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed_names["math"] = math
    allowed_names["abs"] = abs
    allowed_names["round"] = round
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"

@tool
def run_python_code(code: str) -> str:
    """Executes arbitrary Python code and returns captured standard output."""
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exec(code, {"__name__": "__main__"})
        output = buffer.getvalue().strip()
        return output if output else "[Code executed successfully with no output]"
    except Exception as e:
        return f"Runtime error: {type(e).__name__}: {e}"

# =====================================================================
# Robust File Operations (Claude Code & Antigravity Style)
# =====================================================================

MAX_READ_FILE_BYTES = 512 * 1024  # 512 KB safe context threshold

def _read_text_safely(abs_path: str, max_bytes: int = MAX_READ_FILE_BYTES) -> tuple[str, bool, str]:
    """
    Reads file bytes, detects text encoding (including UTF-16 LE/BE, UTF-8 with BOM),
    and decodes safely.
    Returns: (content_string, is_truncated, encoding_used)
    Raises: ValueError if truly binary.
    """
    with open(abs_path, "rb") as f:
        raw = f.read(max_bytes + 1)

    truncated = len(raw) > max_bytes
    data = raw[:max_bytes]

    # Check for BOMs
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16", errors="replace"), truncated, "utf-16"
    elif data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace"), truncated, "utf-16"
    elif data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace"), truncated, "utf-8-sig"

    # Null byte check for binary files vs UTF-16 without BOM
    if b"\x00" in data[:4096]:
        try:
            sample = data[:512].decode("utf-16-le")
            printable = sum(1 for c in sample if c.isprintable() or c in "\r\n\t")
            if len(sample) > 0 and printable / len(sample) > 0.75:
                return data.decode("utf-16-le", errors="replace"), truncated, "utf-16-le"
        except Exception:
            pass
        raise ValueError("Binary file detected")

    try:
        return data.decode("utf-8"), truncated, "utf-8"
    except UnicodeDecodeError:
        try:
            return data.decode("cp1252", errors="replace"), truncated, "cp1252"
        except Exception:
            return data.decode("latin-1", errors="replace"), truncated, "latin-1"

@tool
def read_file(filepath: str) -> str:
    """Reads and returns the content of a local text or document file. For large files (>500KB), automatically summarizes or suggests using read_file_range."""
    try:
        abs_path = resolve_path(filepath)
        if not os.path.exists(abs_path):
            return f"File not found: '{filepath}' (resolved: '{abs_path}')"

        if os.path.isdir(abs_path):
            return list_directory(abs_path)

        ext = os.path.splitext(abs_path)[1].lower()
        if ext in ('.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv', '.tsv'):
            return read_document(abs_path)

        file_size = os.path.getsize(abs_path)
        if file_size > 5 * 1024 * 1024:
            return f"File '{filepath}' is too large ({file_size / (1024*1024):.1f} MB) to read entirely into context. Use 'read_file_range' or 'search_file_contents' instead."

        try:
            content, truncated, enc = _read_text_safely(abs_path, MAX_READ_FILE_BYTES)
        except ValueError:
            return f"File '{filepath}' is a binary file ({file_size} bytes). Cannot read as text."

        if truncated:
            line_count = len(content.splitlines())
            return content + f"\n\n... [Truncated after {MAX_READ_FILE_BYTES // 1024} KB / ~{line_count} lines. Use read_file_range to view remaining lines.]"

        return content if content else "[File is empty]"
    except Exception as e:
        return f"Error reading file '{filepath}': {type(e).__name__}: {e}"

@tool
def write_file(filepath: str, content: str) -> str:
    """Writes or overwrites text content to a local file atomically. Creates parent directories automatically."""
    try:
        abs_path = resolve_path(filepath)
        if os.path.isdir(abs_path):
            return f"Error writing file: '{abs_path}' is an existing directory."

        dir_name = os.path.dirname(abs_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        is_new = not os.path.exists(abs_path)

        # Check existing file line endings
        existing_crlf = False
        if not is_new:
            try:
                with open(abs_path, "rb") as f:
                    existing_bytes = f.read(4096)
                    existing_crlf = b"\r\n" in existing_bytes
            except Exception:
                pass

        write_content = content
        if existing_crlf:
            write_content = write_content.replace("\r\n", "\n").replace("\n", "\r\n")

        # Atomic write via temporary file
        tmp_name = f".{os.path.basename(abs_path)}.{uuid.uuid4().hex[:6]}.tmp"
        tmp_path = os.path.join(dir_name or ".", tmp_name)

        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            f.write(write_content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, abs_path)

        lines = len(content.splitlines()) if content else 0
        byte_size = len(write_content.encode("utf-8"))
        status = "Created" if is_new else "Updated"
        return f"Successfully {status.lower()} '{abs_path}' ({status}, +{lines} lines, {byte_size} bytes)"
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return f"Error writing file '{filepath}': {type(e).__name__}: {e}"

@tool
def replace_in_file(filepath: str, target: str, replacement: str, allow_multiple: bool = False) -> str:
    """
    Surgically replaces an exact target code block with a replacement string in a file.
    Handles CRLF/LF line-ending discrepancies, encodings (UTF-8, UTF-16), and whitespace normalization gracefully.
    If target occurs multiple times, requires allow_multiple=True or sufficient context lines to be unique.
    """
    if not target:
        return "Error: 'target' string cannot be empty."

    try:
        abs_path = resolve_path(filepath)
        if not os.path.exists(abs_path):
            return f"File not found: '{filepath}' (resolved: '{abs_path}')"
        if os.path.isdir(abs_path):
            return f"Error: '{abs_path}' is a directory, not a file."

        with open(abs_path, "rb") as f:
            raw_bytes = f.read()

        # Encoding detection
        encoding = "utf-8"
        has_crlf = b"\r\n" in raw_bytes
        if raw_bytes.startswith(b"\xff\xfe"):
            encoding = "utf-16"
            content = raw_bytes.decode("utf-16", errors="replace")
        elif raw_bytes.startswith(b"\xfe\xff"):
            encoding = "utf-16"
            content = raw_bytes.decode("utf-16", errors="replace")
        elif raw_bytes.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
            content = raw_bytes.decode("utf-8-sig", errors="replace")
        elif b"\x00" in raw_bytes[:4096]:
            try:
                content = raw_bytes.decode("utf-16-le")
                encoding = "utf-16-le"
            except Exception:
                return f"Error: '{filepath}' appears to be a binary file."
        else:
            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_bytes.decode("cp1252", errors="replace")
                encoding = "cp1252"

        # Normalize newlines in content, target, and replacement to \n
        norm_content = content.replace("\r\n", "\n")
        norm_target = target.replace("\r\n", "\n")
        norm_replacement = replacement.replace("\r\n", "\n")

        content_lines = norm_content.splitlines(keepends=True)
        target_lines = norm_target.splitlines(keepends=True)
        target_stripped_lines = [l.rstrip("\r\n") for l in target_lines]

        # Strategy 1: Exact match on normalized content
        match_idx = norm_content.find(norm_target)
        if match_idx != -1:
            count = norm_content.count(norm_target)
            if count > 1 and not allow_multiple:
                line_nums = []
                pos = 0
                for _ in range(count):
                    pos = norm_content.find(norm_target, pos)
                    line_num = norm_content[:pos].count("\n") + 1
                    line_nums.append(str(line_num))
                    pos += len(norm_target)
                return (
                    f"Target string found {count} times in '{filepath}' (at lines: {', '.join(line_nums)}). "
                    f"To prevent accidental edits, provide more surrounding context lines to make the target unique, "
                    f"or set allow_multiple=True."
                )
            if allow_multiple:
                new_content = norm_content.replace(norm_target, norm_replacement)
                replaced_count = count
            else:
                new_content = norm_content.replace(norm_target, norm_replacement, 1)
                replaced_count = 1

        else:
            # Strategy 2: Line-by-line sliding window match (tolerant of trailing whitespace differences)
            window_size = len(target_lines)
            if window_size == 0:
                return "Error: Target contains no lines."

            matching_windows = []
            for i in range(len(content_lines) - window_size + 1):
                window = content_lines[i : i + window_size]
                window_stripped = [l.rstrip("\r\n") for l in window]

                matched = True
                for k in range(window_size):
                    if window_stripped[k].rstrip() != target_stripped_lines[k].rstrip():
                        matched = False
                        break
                if matched:
                    matching_windows.append(i)

            if not matching_windows:
                hint = ""
                first_target_line = target_stripped_lines[0].strip() if target_stripped_lines else ""
                if first_target_line:
                    matching_first_lines = [
                        str(idx + 1) for idx, l in enumerate(content_lines)
                        if first_target_line in l
                    ]
                    if matching_first_lines:
                        hint = f" Note: First line was found at line(s) {', '.join(matching_first_lines[:5])}, but surrounding lines did not match. Check indentation and context."
                return f"Target string not found in '{filepath}'.{hint}"

            count = len(matching_windows)
            if count > 1 and not allow_multiple:
                line_nums = [str(w + 1) for w in matching_windows]
                return (
                    f"Target string found {count} times in '{filepath}' (at lines: {', '.join(line_nums)}). "
                    f"To prevent accidental edits, provide more surrounding context lines to make the target unique, "
                    f"or set allow_multiple=True."
                )

            windows_to_replace = matching_windows if allow_multiple else [matching_windows[0]]
            replaced_count = len(windows_to_replace)

            repl_lines = norm_replacement.splitlines(keepends=True)
            new_lines = list(content_lines)
            for start_idx in reversed(windows_to_replace):
                new_lines[start_idx : start_idx + window_size] = repl_lines

            new_content = "".join(new_lines)

        # Re-apply line endings
        if has_crlf:
            new_content = new_content.replace("\r\n", "\n").replace("\n", "\r\n")

        # Atomic write
        out_bytes = new_content.encode(encoding, errors="replace")
        dir_name = os.path.dirname(abs_path) or "."
        tmp_name = f".{os.path.basename(abs_path)}.{uuid.uuid4().hex[:6]}.tmp"
        tmp_path = os.path.join(dir_name, tmp_name)
        with open(tmp_path, "wb") as f:
            f.write(out_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)

        t_lines = len(norm_target.splitlines())
        r_lines = len(norm_replacement.splitlines())
        diff_lines = r_lines - t_lines
        sign = f"+{diff_lines}" if diff_lines >= 0 else f"{diff_lines}"
        mult_info = f" ({replaced_count} occurrences replaced)" if replaced_count > 1 else ""

        return f"Successfully updated '{abs_path}': replaced {t_lines} lines with {r_lines} lines ({sign} lines){mult_info}"
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return f"Error replacing text in '{filepath}': {type(e).__name__}: {e}"

@tool
def read_file_range(filepath: str, start_line: int = 1, end_line: int = 100) -> str:
    """Reads a specific slice of lines from a file (1-indexed). Prevents blowing token context on large files."""
    try:
        abs_path = resolve_path(filepath)
        if not os.path.exists(abs_path):
            return f"File not found: '{filepath}' (resolved: '{abs_path}')"
        if os.path.isdir(abs_path):
            return f"Path '{filepath}' is a directory, not a file. Use 'list_directory' instead."

        try:
            full_text, _, _ = _read_text_safely(abs_path, max_bytes=10 * 1024 * 1024)
        except ValueError:
            return f"File '{filepath}' is a binary file. Cannot read lines as text."

        lines = full_text.splitlines()
        total = len(lines)
        start = max(1, int(start_line))
        end = min(total, int(end_line))

        if total == 0:
            return f"File '{filepath}' is empty (0 lines)."
        if start > total:
            return f"Start line {start} is beyond file length ({total} lines in '{filepath}')."

        output = [f"Showing lines {start} to {end} of {total} in '{abs_path}':"]
        for i in range(start - 1, end):
            output.append(f"{i + 1}: {lines[i]}")
        return "\n".join(output)
    except Exception as e:
        return f"Error reading file range for '{filepath}': {e}"

@tool
def list_directory(directory_path: str = ".") -> str:
    """Lists files and folders inside the specified directory path."""
    try:
        abs_path = resolve_path(directory_path)
        if not os.path.exists(abs_path):
            return f"Directory not found: '{directory_path}' (resolved: '{abs_path}')"
        if not os.path.isdir(abs_path):
            return f"Path is not a directory: '{abs_path}'"

        entries = sorted(os.listdir(abs_path))
        if not entries:
            return f"[Empty directory: {abs_path}]"

        formatted = []
        max_show = 150
        for e in entries[:max_show]:
            p = os.path.join(abs_path, e)
            if os.path.isdir(p):
                formatted.append(f"[DIR]  {e}/")
            else:
                try:
                    sz = os.path.getsize(p)
                    sz_str = f"{sz / 1024:.1f} KB" if sz > 1024 else f"{sz} B"
                except Exception:
                    sz_str = ""
                formatted.append(f"[FILE] {e} ({sz_str})")

        if len(entries) > max_show:
            formatted.append(f"... and {len(entries) - max_show} more items.")

        return f"Contents of '{abs_path}':\n" + "\n".join(formatted)
    except Exception as e:
        return f"Error listing directory '{directory_path}': {e}"

@tool
def find_files(name_pattern: str, search_dir: str = ".", max_results: int = 50) -> str:
    """Rapidly searches for files matching a glob pattern (e.g. '*.py', '*report*.docx', 'config.*') across directories, skipping bloated junk folders."""
    import fnmatch
    try:
        resolved_dir = resolve_path(search_dir)
        if not os.path.exists(resolved_dir):
            return f"Directory not found: '{search_dir}' (resolved: '{resolved_dir}')"

        ignore = {
            '.git', 'node_modules', '__pycache__', '.venv', 'venv', '$recycle.bin',
            'appdata', '.cache', 'dist', 'build', '.gemini', '.vscode', 'windows',
            '.idea', '.vs', 'obj', 'bin', '.harness'
        }
        matches = []
        raw_pat = name_pattern.strip().lower().replace("\\", "/")
        has_wildcard = any(c in raw_pat for c in ("*", "?", "["))

        for root, dirs, files in os.walk(resolved_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ignore and not d.startswith('.')]

            for f in files:
                rel_path = os.path.relpath(os.path.join(root, f), resolved_dir).replace("\\", "/").lower()
                f_lower = f.lower()

                matched = False
                if fnmatch.fnmatch(f_lower, raw_pat) or fnmatch.fnmatch(rel_path, raw_pat):
                    matched = True
                elif not has_wildcard:
                    if raw_pat in f_lower or raw_pat in rel_path:
                        matched = True
                    elif fnmatch.fnmatch(f_lower, f"*{raw_pat}*"):
                        matched = True

                if matched:
                    full_path = os.path.normpath(os.path.join(root, f))
                    try:
                        sz = os.path.getsize(full_path)
                        sz_str = f"{sz / 1024:.1f} KB" if sz > 1024 else f"{sz} B"
                    except Exception:
                        sz_str = "unknown size"
                    matches.append((full_path, sz_str))
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No files matching '{name_pattern}' found in '{resolved_dir}'."
        header = f"Found {len(matches)} matching file(s) for '{name_pattern}' in '{resolved_dir}':\n"
        return header + "\n".join(f"{p} ({sz})" for p, sz in matches)
    except Exception as e:
        return f"Error searching files: {e}"

@tool
def search_file_contents(query: str, search_dir: str = ".", extension: str = "", max_results: int = 40) -> str:
    """Fast deep grep across text files in a directory or computer folder. Returns matching file paths, line numbers, and snippets."""
    try:
        resolved_path = resolve_path(search_dir)
        if not os.path.exists(resolved_path):
            return f"Path not found: '{search_dir}' (resolved: '{resolved_path}')"

        q = query.lower()
        matches = []

        # Single file search support
        if os.path.isfile(resolved_path):
            try:
                content, _, _ = _read_text_safely(resolved_path, max_bytes=5 * 1024 * 1024)
                for line_no, line in enumerate(content.splitlines(), 1):
                    if q in line.lower():
                        snippet = line.strip()[:140]
                        matches.append(f"{resolved_path}:{line_no}: {snippet}")
                        if len(matches) >= max_results:
                            break
            except Exception as e:
                return f"Error searching '{resolved_path}': {e}"

            if not matches:
                return f"No occurrences of '{query}' found in '{resolved_path}'."
            header = f"Found {len(matches)} match(es) for '{query}' in '{resolved_path}':\n"
            return header + "\n".join(matches)

        ignore = {
            '.git', 'node_modules', '__pycache__', '.venv', 'venv', '$recycle.bin',
            'appdata', '.cache', 'dist', 'build', '.gemini', '.vscode', 'windows',
            '.idea', '.vs', 'obj', 'bin', '.harness'
        }
        ext = extension.lower() if not extension or extension.startswith('.') else f".{extension.lower()}"

        for root, dirs, files in os.walk(resolved_path):
            dirs[:] = [d for d in dirs if d.lower() not in ignore and not d.startswith('.')]
            for f in files:
                if ext and not f.lower().endswith(ext):
                    continue
                path = os.path.normpath(os.path.join(root, f))
                try:
                    if os.path.getsize(path) > 2 * 1024 * 1024:
                        continue
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        for line_no, line in enumerate(fp, 1):
                            if q in line.lower():
                                snippet = line.strip()[:140]
                                matches.append(f"{path}:{line_no}: {snippet}")
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No occurrences of '{query}' found in '{resolved_path}'."
        header = f"Found {len(matches)} match(es) for '{query}' in '{resolved_path}':\n"
        return header + "\n".join(matches)
    except Exception as e:
        return f"Error searching file contents: {e}"

@tool
def read_document(filepath: str, max_chars: int = 8000) -> str:
    """Universal document reader. Extracts clean text from .pdf, .docx, .doc, .pptx, .xlsx, .csv, and code/text files."""
    try:
        expanded = resolve_path(filepath)
        if not os.path.exists(expanded):
            return f"File not found: '{filepath}' (resolved: '{expanded}')"
        ext = os.path.splitext(expanded)[1].lower()

        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(expanded)
            total_pages = len(reader.pages)
            pages_text = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages_text.append(f"--- Page {i + 1} of {total_pages} ---\n{txt.strip()}")
            text = "\n\n".join(pages_text) if pages_text else "[PDF contains no extractable text (may be image-only scan)]"

        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(expanded)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            tables = []
            for t_idx, table in enumerate(doc.tables):
                t_rows = []
                for row in table.rows:
                    t_rows.append(" | ".join(c.text.strip() for c in row.cells))
                if t_rows:
                    tables.append(f"[Table {t_idx + 1}]\n" + "\n".join(t_rows))
            all_parts = paras + tables
            text = "\n\n".join(all_parts) if all_parts else "[Document is empty]"

        elif ext in (".pptx", ".ppt"):
            import pptx
            pres = pptx.Presentation(expanded)
            slides_text = []
            for i, slide in enumerate(pres.slides):
                s_text = []
                for shape in slide.shapes:
                    if shape.has_text_frame and shape.text.strip():
                        s_text.append(shape.text.strip())
                if s_text:
                    slides_text.append(f"--- Slide {i + 1} ---\n" + "\n".join(s_text))
            text = "\n\n".join(slides_text) if slides_text else "[Presentation contains no text]"

        elif ext in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(expanded, data_only=True)
            sheets_text = []
            for sname in wb.sheetnames[:5]:
                ws = wb[sname]
                rows = []
                for row in ws.iter_rows(values_only=True):
                    if any(c is not None for c in row):
                        rows.append(" | ".join(str(c) if c is not None else "" for c in row))
                if rows:
                    sheets_text.append(f"--- Sheet: {sname} ---\n" + "\n".join(rows[:100]))
            text = "\n\n".join(sheets_text) if sheets_text else "[Workbook is empty]"

        elif ext in (".csv", ".tsv"):
            delimiter = "\t" if ext == ".tsv" else ","
            import csv
            with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = [" | ".join(row) for row in reader if row]
            text = "\n".join(rows[:150]) if rows else "[CSV file is empty]"

        else:
            with open(expanded, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [Truncated after {max_chars} characters]"
        return text if text.strip() else "[File is empty]"

    except Exception as e:
        return f"Error reading document '{filepath}': {type(e).__name__}: {e}"

@tool
def open_file(filepath: str) -> str:
    """Launches a file or folder in its default Windows desktop application or reveals it in File Explorer."""
    try:
        expanded = resolve_path(filepath)
        if not os.path.exists(expanded):
            return f"Path not found: '{filepath}' (resolved: '{expanded}')"
        os.startfile(expanded)
        return f"Successfully opened '{expanded}' in Windows default application."
    except Exception as e:
        return f"Error opening '{filepath}': {e}"

@tool
def inspect_image(filepath: str, question: str = "Describe this image in detail and extract all visible text.") -> str:
    """Inspects an image (.png, .jpg, .jpeg, .webp) using AI Vision and OCR. Answers questions about its content, diagrams, or text."""
    import base64
    import mimetypes
    import urllib.request
    import json
    import config

    try:
        expanded = resolve_path(filepath)
        if not os.path.exists(expanded):
            return f"Image file not found: '{filepath}' (resolved: '{expanded}')"

        mime_type, _ = mimetypes.guess_type(expanded)
        if not mime_type or not mime_type.startswith("image/"):
            ext = os.path.splitext(expanded)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.webp'):
                mime_type = f"image/{ext.lstrip('.')}"
                if ext == '.jpg': mime_type = 'image/jpeg'
            else:
                return f"Unsupported image format '{ext}'. Supported: png, jpg, jpeg, webp."

        with open(expanded, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        prof = config.PROFILES.get("gemini", {})
        base_url = prof.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
        api_key = prof.get("api_key", "")
        model = prof.get("model", "gemini-flash-lite-latest")

        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
                    ]
                }
            ]
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"].get("content", "[No description generated]")
    except Exception as e:
        return f"Error analyzing image '{filepath}': {type(e).__name__}: {e}"

@tool
def download_file(url: str, destination_path: str) -> str:
    """Downloads a file from any web URL and saves it to a local file path."""
    import requests
    try:
        expanded = resolve_path(destination_path)
        dir_name = os.path.dirname(expanded)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with requests.get(url, headers=headers, stream=True, timeout=45) as r:
            r.raise_for_status()
            total_size = 0
            tmp_target = f"{expanded}.{uuid.uuid4().hex[:6]}.tmp"
            with open(tmp_target, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_target, expanded)

        sz_str = f"{total_size / 1024:.1f} KB" if total_size < 1024 * 1024 else f"{total_size / (1024 * 1024):.2f} MB"
        return f"Successfully downloaded '{url}' to '{expanded}' ({sz_str})."
    except Exception as e:
        if 'tmp_target' in locals() and os.path.exists(tmp_target):
            try:
                os.remove(tmp_target)
            except Exception:
                pass
        return f"Error downloading from '{url}': {type(e).__name__}: {e}"

# =====================================================================
# Web Research Tools
# =====================================================================

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Searches DuckDuckGo on the live web and returns top matching pages with titles, URLs, and snippets."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return f"No search results found for query: '{query}'"

            formatted = []
            for i, r in enumerate(results, 1):
                title = r.get("title", "No Title")
                href = r.get("href", "")
                snippet = r.get("body", "")
                formatted.append(f"[{i}] {title}\n    URL: {href}\n    Snippet: {snippet}")
            return "\n\n".join(formatted)
    except Exception as e:
        return f"Web search error: {type(e).__name__}: {e}"

@tool
def fetch_webpage(url: str, max_chars: int = 5000) -> str:
    """Fetches a webpage URL and extracts its main clean readable text content."""
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [Truncated after {max_chars} characters]"
        return text if text else "[Page returned empty text content]"
    except Exception as e:
        return f"Error fetching webpage '{url}': {type(e).__name__}: {e}"

# =====================================================================
# Memory & Knowledge Tools
# =====================================================================

@tool
def save_memory(key: str, note_or_rule: str) -> str:
    """Permanently saves a user preference, folder path, or instruction across all sessions, reboots, and project switches."""
    from harness.memory import save_memory_entry
    try:
        save_memory_entry(key, note_or_rule)
        return f"Successfully saved memory '[{key}]'. It is now permanently active across all sessions, project switches, and reboots."
    except Exception as e:
        return f"Error saving memory: {e}"

@tool
def recall_memory(key: str = "") -> str:
    """Recalls saved persistent memories. If key is provided, returns that specific memory; otherwise lists all active memories."""
    from harness.memory import load_memories
    try:
        memories = load_memories()
        if not memories:
            return "No persistent memories currently saved. Use save_memory to add some."
        if key and key.strip() in memories:
            item = memories[key.strip()]
            val = item.get("value", "") if isinstance(item, dict) else str(item)
            return f"[{key.strip()}]: {val}"
        elif key:
            return f"No memory found matching '{key}'."

        formatted = ["Current Persistent Memories:"]
        for k, v in memories.items():
            val = v.get("value", "") if isinstance(v, dict) else str(v)
            formatted.append(f"- [{k}]: {val}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error recalling memory: {e}"

@tool
def delete_memory(key: str) -> str:
    """Permanently removes a saved memory key."""
    from harness.memory import delete_memory_entry
    try:
        if delete_memory_entry(key):
            return f"Successfully deleted memory '[{key}]'."
        return f"Memory key '[{key}]' not found."
    except Exception as e:
        return f"Error deleting memory: {e}"

@tool
def save_project_knowledge(key: str, value: str) -> str:
    """Saves a project-specific knowledge note or architectural decision permanently to .harness/knowledge.json inside the active project folder."""
    try:
        from harness.memory import save_project_knowledge as _spk
        ws = get_active_workspace()
        _spk(key, value, ws)
        return f"Successfully saved project knowledge for '{os.path.basename(ws)}': [{key}] = '{value}'"
    except Exception as e:
        return f"Error saving project knowledge: {e}"

# =====================================================================
# Project & Workspace Tools
# =====================================================================

@tool
def get_workspace() -> str:
    """Returns the current active project workspace directory path and top-level files."""
    try:
        ws = get_active_workspace()
        entries = sorted(os.listdir(ws)) if os.path.exists(ws) else []
        summary = "\n".join(f"  - {e}" for e in entries[:25])
        more = f"\n  ... and {len(entries) - 25} more items" if len(entries) > 25 else ""
        return f"Active Workspace: {ws}\nFiles:\n{summary}{more}" if entries else f"Active Workspace: {ws}\n[Empty workspace]"
    except Exception as e:
        return f"Active Workspace: {get_active_workspace()} (Error reading directory: {e})"

@tool
def set_workspace(directory_path: str) -> str:
    """Switches the active project workspace directory for all file operations and shell commands. Creates the directory if it does not exist."""
    try:
        resolved = resolve_path(directory_path)
        os.makedirs(resolved, exist_ok=True)
        new_ws = set_active_workspace(resolved)
        return f"Workspace successfully switched to: {new_ws}"
    except Exception as e:
        return f"Error setting workspace to '{directory_path}': {e}"

@tool
def create_project(project_name: str, parent_directory: str = "", template: str = "python") -> str:
    """Creates a new project folder with scaffolding (README, .gitignore, starter file) and sets it as the active workspace."""
    try:
        base_dir = resolve_path(parent_directory) if parent_directory else get_active_workspace()
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', str(project_name)).strip()
        if not clean_name:
            clean_name = "new_project"
        target_dir = os.path.join(base_dir, clean_name)
        os.makedirs(target_dir, exist_ok=True)

        readme_path = os.path.join(target_dir, "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"# {clean_name}\n\nProject initialized by John's Harness.\n")

        gitignore_path = os.path.join(target_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("__pycache__/\n*.pyc\nnode_modules/\n.env\n.DS_Store\n.harness/\n")

        tmpl = template.lower().strip()
        if tmpl in ("python", "py"):
            main_py = os.path.join(target_dir, "main.py")
            if not os.path.exists(main_py):
                with open(main_py, "w", encoding="utf-8") as f:
                    f.write(f'"""\n{clean_name} entry point\n"""\n\ndef main():\n    print("Hello from {clean_name}!")\n\nif __name__ == "__main__":\n    main()\n')
        elif tmpl in ("web", "html", "js", "frontend"):
            index_html = os.path.join(target_dir, "index.html")
            if not os.path.exists(index_html):
                with open(index_html, "w", encoding="utf-8") as f:
                    f.write(f'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <title>{clean_name}</title>\n</head>\n<body>\n  <h1>{clean_name}</h1>\n</body>\n</html>\n')

        new_ws = set_active_workspace(target_dir)
        return f"Successfully created project '{clean_name}' at {new_ws} and set as active workspace."
    except Exception as e:
        return f"Error creating project '{project_name}': {e}"

def _git_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    env["GH_PROMPT_DISABLED"] = "1"
    env["NO_COLOR"] = "1"
    return env

_WIN_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def find_repo_root(start_dir: Optional[str] = None) -> str:
    """Finds the nearest git repository root directory by walking up from start_dir.
    Falls back to the repository root where the harness source lives, or the active workspace."""
    start = canonical_path(start_dir or get_active_workspace())
    curr = start
    while curr:
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.dirname(script_dir),
        script_dir,
        os.path.abspath(os.path.join(script_dir, "..", "..", "..", "..")),
        r"C:\Users\User\Downloads\Johns dangerous harness",
    ]
    for c in candidates:
        if c and os.path.exists(os.path.join(c, ".git")):
            return canonical_path(c)

    return start

def _run_git_cmd(cmd: List[str], cwd: str, timeout: int = 25) -> subprocess.CompletedProcess:
    """Executes a git or gh CLI command with DEVNULL stdin and tight timeout to prevent IPC deadlocks."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_git_env(),
        creationflags=_WIN_NO_WINDOW,
        timeout=timeout
    )

@tool
def git_init(repo_dir: str = ".") -> str:
    """Initializes a new Git repository in the specified directory (defaults to active workspace)."""
    try:
        target = resolve_path(repo_dir)
        os.makedirs(target, exist_ok=True)
        if os.path.exists(os.path.join(target, ".git")):
            return f"Git repository is already initialized at: {target}"
        res = _run_git_cmd(["git", "init", "-b", "main"], cwd=target, timeout=10)
        if res.returncode != 0:
            res = _run_git_cmd(["git", "init"], cwd=target, timeout=10)
            if res.returncode != 0:
                return f"Git init failed: {res.stderr.strip() or res.stdout.strip()}"
            _run_git_cmd(["git", "branch", "-M", "main"], cwd=target, timeout=5)
        return f"Successfully initialized empty Git repository at: {target}\n{res.stdout.strip()}"
    except Exception as e:
        return f"Error initializing git repository: {e}"

@tool
def git_remote_add(remote_url: str, remote_name: str = "origin", repo_dir: str = ".") -> str:
    """Adds or updates a remote git repository URL (e.g. 'https://github.com/user/repo.git')."""
    try:
        target = resolve_path(repo_dir)
        if not os.path.exists(os.path.join(target, ".git")):
            return f"Error: Directory '{target}' is not a git repository. Use 'git_init' first."

        chk = _run_git_cmd(["git", "remote"], cwd=target, timeout=8)
        remotes = [r.strip() for r in chk.stdout.splitlines() if r.strip()]
        if remote_name in remotes:
            cmd = ["git", "remote", "set-url", remote_name, remote_url.strip()]
            action = "updated"
        else:
            cmd = ["git", "remote", "add", remote_name, remote_url.strip()]
            action = "added"

        res = _run_git_cmd(cmd, cwd=target, timeout=10)
        if res.returncode != 0:
            return f"Git remote failed: {res.stderr.strip() or res.stdout.strip()}"
        return f"Successfully {action} remote '{remote_name}' -> {remote_url.strip()}"
    except Exception as e:
        return f"Error configuring git remote: {e}"

@tool
def git_status(repo_dir: str = ".") -> str:
    """Checks git repository status (branch, modified files, untracked files, ahead/behind status)."""
    try:
        target = find_repo_root(resolve_path(repo_dir))
        if not os.path.exists(os.path.join(target, ".git")):
            return f"Directory '{target}' is not a git repository. Use 'git_init' to initialize git here if desired."

        res = _run_git_cmd(["git", "--no-optional-locks", "status", "--short", "--branch"], cwd=target, timeout=10)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Git error (exit code {res.returncode}): {err}"

        lines = res.stdout.strip().splitlines()
        branch_line = lines[0] if lines else "## No branch info"
        file_lines = lines[1:] if len(lines) > 1 else []

        log_res = _run_git_cmd(["git", "--no-pager", "log", "-1", "--oneline"], cwd=target, timeout=8)
        last_commit = log_res.stdout.strip() if log_res.returncode == 0 else "None (no commits yet)"

        summary = [
            f"Git Status for: {target}",
            f"Branch: {branch_line.lstrip('# ')}",
            f"Last Commit: {last_commit}"
        ]

        if file_lines:
            summary.append(f"\nChanged Files ({len(file_lines)}):")
            for f in file_lines[:60]:
                summary.append(f"  {f}")
            if len(file_lines) > 60:
                summary.append(f"  ... ({len(file_lines) - 60} more files omitted)")
        else:
            summary.append("\nWorking tree clean (no uncommitted changes).")

        return "\n".join(summary)
    except subprocess.TimeoutExpired:
        return f"Git command timed out in '{repo_dir}'."
    except Exception as e:
        return f"Error checking git status: {e}"

@tool
def git_diff(filepath: str = "", staged: bool = False, repo_dir: str = ".") -> str:
    """Inspects git line-by-line diffs for uncommitted or staged changes. Prevents token overload by limiting output length."""
    try:
        target_dir = find_repo_root(resolve_path(repo_dir))
        if not os.path.exists(os.path.join(target_dir, ".git")):
            return f"Directory '{target_dir}' is not a git repository."

        cmd = ["git", "--no-pager", "diff"]
        if staged:
            cmd.append("--cached")
        if filepath:
            clean_fp = resolve_path(filepath, base_dir=target_dir)
            rel_fp = os.path.relpath(clean_fp, target_dir)
            cmd.extend(["--", rel_fp])

        res = _run_git_cmd(cmd, cwd=target_dir, timeout=15)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Git diff error (exit code {res.returncode}): {err}"

        diff_text = res.stdout
        if not diff_text.strip():
            mode = "staged" if staged else "unstaged"
            target_desc = f" for '{filepath}'" if filepath else ""
            return f"No {mode} changes found{target_desc} in '{target_dir}'."

        lines = diff_text.splitlines()
        max_lines = 400
        if len(lines) > max_lines:
            truncated = "\n".join(lines[:max_lines])
            return (
                f"{truncated}\n\n"
                f"[Output Truncated: Showing first {max_lines} of {len(lines)} diff lines to conserve context. "
                f"Use 'filepath' parameter to inspect specific files.]"
            )
        return diff_text
    except subprocess.TimeoutExpired:
        return f"Git diff command timed out in '{repo_dir}'."
    except Exception as e:
        return f"Error retrieving git diff: {e}"

@tool
def git_commit_and_push(commit_message: str = "", message: str = "", msg: str = "", branch: str = "", add_all: bool = True, repo_dir: str = ".") -> str:
    """Stages changes, creates a git commit, and pushes to remote repository using configured git credentials."""
    try:
        target_dir = find_repo_root(resolve_path(repo_dir))
        if not os.path.exists(os.path.join(target_dir, ".git")):
            return f"Error: '{target_dir}' is not a git repository. Call 'git_init' first."

        effective_msg = (commit_message or message or msg or "").strip()
        if not effective_msg:
            effective_msg = "Update files via John's Harness"

        # Determine current branch
        br_res = _run_git_cmd(["git", "branch", "--show-current"], cwd=target_dir, timeout=8)
        curr_br = br_res.stdout.strip() or branch or "main"
        if not curr_br:
            _run_git_cmd(["git", "branch", "-M", "main"], cwd=target_dir, timeout=5)
            curr_br = "main"

        # Check remote origin
        rem_chk = _run_git_cmd(["git", "remote"], cwd=target_dir, timeout=8)
        has_remote = "origin" in [r.strip() for r in rem_chk.stdout.splitlines()]

        if add_all:
            add_res = _run_git_cmd(["git", "add", "-A"], cwd=target_dir, timeout=20)
            if add_res.returncode != 0:
                return f"Git add failed: {add_res.stderr.strip() or add_res.stdout.strip()}"

        commit_res = _run_git_cmd(["git", "commit", "-m", effective_msg], cwd=target_dir, timeout=20)
        commit_out = (commit_res.stdout.strip() + "\n" + commit_res.stderr.strip()).strip()
        if commit_res.returncode != 0:
            if "nothing to commit" not in commit_out.lower():
                return f"Git commit failed: {commit_out}"

        if not has_remote:
            return f"Committed successfully ({effective_msg}), but no remote 'origin' is configured yet. Use 'github_create_repo' or 'git_remote_add' to push to GitHub."

        push_res = _run_git_cmd(["git", "push", "-u", "origin", curr_br], cwd=target_dir, timeout=30)
        push_out = (push_res.stdout.strip() + "\n" + push_res.stderr.strip()).strip()
        if push_res.returncode != 0:
            # Fallback to plain push
            push_res2 = _run_git_cmd(["git", "push"], cwd=target_dir, timeout=30)
            if push_res2.returncode == 0:
                push_out = (push_res2.stdout.strip() + "\n" + push_res2.stderr.strip()).strip()
            else:
                return f"Commit succeeded ({effective_msg}), but push failed:\n{push_out}\n{push_res2.stderr.strip()}"

        return f"Git Commit & Push Successful (branch: {curr_br})!\nCommit: {effective_msg}\nDetails:\n{commit_out}\n{push_out}".strip()
    except subprocess.TimeoutExpired:
        return "Git operation timed out."
    except Exception as e:
        return f"Error executing git commit and push: {e}"

@tool
def github_create_repo(repo_name: str = "", name: str = "", private: bool = False, repo_dir: str = ".") -> str:
    """Creates a new repository on GitHub for the current project using the GitHub CLI (gh) and pushes code."""
    try:
        target_dir = resolve_path(repo_dir)
        effective_name = (repo_name or name or os.path.basename(target_dir) or "my-app").strip()
        vis_flag = "--private" if private else "--public"

        # 1. Ensure git repository is initialized
        if not os.path.exists(os.path.join(target_dir, ".git")):
            init_res = _run_git_cmd(["git", "init", "-b", "main"], cwd=target_dir, timeout=10)
            if init_res.returncode != 0:
                _run_git_cmd(["git", "init"], cwd=target_dir, timeout=10)

        # 2. Ensure main branch
        _run_git_cmd(["git", "branch", "-M", "main"], cwd=target_dir, timeout=8)

        # 3. Ensure initial commit exists
        rev_chk = _run_git_cmd(["git", "rev-parse", "HEAD"], cwd=target_dir, timeout=8)
        if rev_chk.returncode != 0:
            _run_git_cmd(["git", "add", "-A"], cwd=target_dir, timeout=20)
            _run_git_cmd(["git", "commit", "-m", f"Initial commit for {effective_name}"], cwd=target_dir, timeout=20)
        else:
            st_chk = _run_git_cmd(["git", "status", "--porcelain"], cwd=target_dir, timeout=8)
            if st_chk.stdout.strip():
                _run_git_cmd(["git", "add", "-A"], cwd=target_dir, timeout=20)
                _run_git_cmd(["git", "commit", "-m", "Update project files"], cwd=target_dir, timeout=20)

        # 4. Check if remote origin already exists
        rem_check = _run_git_cmd(["git", "remote", "-v"], cwd=target_dir, timeout=8)
        if "origin" in rem_check.stdout:
            push_res = _run_git_cmd(["git", "push", "-u", "origin", "main"], cwd=target_dir, timeout=30)
            return f"Project is already connected to GitHub repository. Pushed latest code to origin/main.\n{push_res.stdout.strip() or push_res.stderr.strip()}"

        # 5. Create repo via GitHub CLI
        cmd = ["gh", "repo", "create", effective_name, vis_flag, "--source=.", "--remote=origin", "--push"]
        res = _run_git_cmd(cmd, cwd=target_dir, timeout=35)
        out = (res.stdout.strip() + "\n" + res.stderr.strip()).strip()

        # 6. Auto-recovery if repo already exists on user's GitHub account
        if res.returncode != 0:
            if "already exists" in out.lower():
                user_res = _run_git_cmd(["gh", "api", "user", "-q", ".login"], cwd=target_dir, timeout=10)
                username = user_res.stdout.strip()
                if username:
                    remote_url = f"https://github.com/{username}/{effective_name}.git"
                    _run_git_cmd(["git", "remote", "add", "origin", remote_url], cwd=target_dir, timeout=8)
                    push_res = _run_git_cmd(["git", "push", "-u", "origin", "main"], cwd=target_dir, timeout=30)
                    return f"Repository '{effective_name}' already existed on GitHub. Connected remote ({remote_url}) and pushed to origin/main.\n{push_res.stdout.strip() or push_res.stderr.strip()}"
            return f"GitHub repo creation failed:\n{out}"

        return f"Successfully created GitHub repository '{effective_name}' and pushed code!\n{out}"
    except Exception as e:
        return f"Error creating GitHub repository: {e}"

@tool
def github_repo_info(repo_dir: str = ".") -> str:
    """Returns details and URLs of the connected GitHub repository using the GitHub CLI (gh)."""
    try:
        target_dir = resolve_path(repo_dir)
        res = _run_git_cmd(["gh", "repo", "view", "--json", "name,owner,url,visibility,isPrivate"], cwd=target_dir, timeout=10)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"GitHub repo info unavailable: {err}"
        return f"GitHub Repository:\n{res.stdout.strip()}"
    except Exception as e:
        return f"Error retrieving GitHub repo info: {e}"

@tool
def copy_file(source: str, destination: str, overwrite: bool = False) -> str:
    """Copies a file or entire directory from source to destination. Creates destination parent folders if needed."""
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)

        if not os.path.exists(src):
            return f"Error: Source path '{src}' does not exist."

        if os.path.exists(dst) and not overwrite:
            return f"Error: Destination '{dst}' already exists. Set overwrite=True to replace it."

        if os.path.isdir(src):
            if os.path.exists(dst) and overwrite:
                shutil.rmtree(dst)
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
            return f"Successfully copied directory from '{src}' to '{dst}'."
        else:
            dst_dir = os.path.dirname(dst)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, dst)
            size_kb = os.path.getsize(dst) / 1024.0
            return f"Successfully copied file from '{src}' to '{dst}' ({size_kb:.1f} KB)."
    except Exception as e:
        return f"Error copying '{source}' to '{destination}': {e}"

@tool
def move_file(source: str, destination: str, overwrite: bool = False) -> str:
    """Moves or renames a file or directory from source to destination. Creates destination parent folders if needed."""
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)

        if not os.path.exists(src):
            return f"Error: Source path '{src}' does not exist."

        if os.path.exists(dst):
            if not overwrite:
                return f"Error: Destination '{dst}' already exists. Set overwrite=True to replace it."
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)

        dst_dir = os.path.dirname(dst)
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)

        shutil.move(src, dst)
        return f"Successfully moved '{src}' to '{dst}'."
    except Exception as e:
        return f"Error moving '{source}' to '{destination}': {e}"

@tool
def delete_file(filepath: str, permanent: bool = False) -> str:
    """Safely deletes a file or directory. By default moves to a local '.trash' archive folder to avoid accidental data loss. Set permanent=True for permanent removal."""
    try:
        target = resolve_path(filepath)

        if not os.path.exists(target):
            return f"Error: Path '{target}' does not exist."

        norm = os.path.normpath(target).lower()
        active_ws_norm = os.path.normpath(get_active_workspace()).lower()
        user_home_norm = os.path.normpath(os.path.expanduser("~")).lower()

        if os.path.splitdrive(norm)[1] in ("\\", "/", ""):
            return f"CRITICAL SAFETY ERROR: Refusing to delete drive root '{target}'."

        protected = ["c:\\windows", "c:\\program files", "c:\\program files (x86)", user_home_norm, active_ws_norm]
        if norm in protected:
            return f"CRITICAL SAFETY ERROR: Refusing to delete protected or root workspace path '{target}'."

        is_directory = os.path.isdir(target)

        if permanent:
            if is_directory:
                shutil.rmtree(target)
                return f"Permanently deleted directory: '{target}'."
            else:
                os.remove(target)
                return f"Permanently deleted file: '{target}'."
        else:
            ws = get_active_workspace()
            trash_dir = os.path.join(ws, ".trash")
            os.makedirs(trash_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.basename(target)
            trash_target = os.path.join(trash_dir, f"{timestamp}_{base_name}")
            shutil.move(target, trash_target)
            item_type = "directory" if is_directory else "file"
            return f"Safely moved {item_type} to trash archive at '{trash_target}'. (Use permanent=True if you wish to permanently destroy)."
    except Exception as e:
        return f"Error deleting '{filepath}': {e}"

# ==============================================================================
# 24/7 Cloud Scrapers & GitHub Actions Automation Tools
# ==============================================================================

@tool
def gh_list_workflows(repo_dir: str = ".") -> str:
    """Lists GitHub Actions workflows in the connected repository, including local workflow files and schedules."""
    try:
        ws = resolve_path(repo_dir)
        repo_root = find_repo_root(ws)

        # 1. Check local .github/workflows directory (in repo_root and ws)
        seen_wfs = set()
        local_files = []
        for check_dir in [os.path.join(repo_root, ".github", "workflows"), os.path.join(ws, ".github", "workflows")]:
            if os.path.exists(check_dir) and os.path.isdir(check_dir):
                for fname in sorted(os.listdir(check_dir)):
                    if fname.endswith((".yml", ".yaml")) and fname not in seen_wfs:
                        seen_wfs.add(fname)
                        fpath = os.path.join(check_dir, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                                content = f.read()
                            cron_match = re.search(r"cron:\s*['\"]([^'\"]+)['\"]", content)
                            name_match = re.search(r"^name:\s*([^\r\n]+)", content, re.MULTILINE)
                            local_files.append({
                                "file": fname,
                                "name": name_match.group(1).strip() if name_match else fname,
                                "cron": cron_match.group(1).strip() if cron_match else "None (Manual)",
                                "path": os.path.relpath(fpath, repo_root).replace("\\", "/")
                            })
                        except Exception:
                            local_files.append({"file": fname, "name": fname, "cron": "Unknown"})

        # 2. Query remote GitHub workflows via gh CLI (executed in repo_root)
        res = _run_git_cmd(["gh", "workflow", "list", "--all"], cwd=repo_root, timeout=12)
        remote_output = res.stdout.strip() if res.returncode == 0 else ""

        # 3. Check scrapers/ directory and any *scraper*.py files in repo_root and ws
        seen_scrapers = set()
        scrapers = []
        search_dirs = [
            os.path.join(repo_root, "scrapers"),
            os.path.join(ws, "scrapers"),
            repo_root,
            ws
        ]
        for sdir in search_dirs:
            if os.path.exists(sdir) and os.path.isdir(sdir):
                for sname in sorted(os.listdir(sdir)):
                    if sname.endswith(".py"):
                        is_scraper = ("scrapers" in sdir) or ("scraper" in sname.lower())
                        if is_scraper and sname not in seen_scrapers:
                            seen_scrapers.add(sname)
                            spath = os.path.join(sdir, sname)
                            if os.path.isfile(spath):
                                scrapers.append({
                                    "file": sname,
                                    "path": os.path.relpath(spath, repo_root).replace("\\", "/"),
                                    "size_bytes": os.path.getsize(spath)
                                })

        # 4. Check scrapers/data/ and output/ directories for saved files
        seen_data = set()
        saved_data = []
        data_dirs = [
            os.path.join(repo_root, "scrapers", "data"),
            os.path.join(ws, "scrapers", "data"),
            os.path.join(repo_root, "output"),
            os.path.join(ws, "output"),
            repo_root,
            ws
        ]
        for ddir in data_dirs:
            if os.path.exists(ddir) and os.path.isdir(ddir):
                for dname in sorted(os.listdir(ddir)):
                    if dname.endswith(".json") and not dname.startswith(".") and dname not in ("package.json", "package-lock.json", "tsconfig.json"):
                        if dname not in seen_data:
                            seen_data.add(dname)
                            dpath = os.path.join(ddir, dname)
                            if os.path.isfile(dpath):
                                saved_data.append({
                                    "file": dname,
                                    "path": os.path.relpath(dpath, repo_root).replace("\\", "/"),
                                    "size_bytes": os.path.getsize(dpath),
                                    "modified": datetime.fromtimestamp(os.path.getmtime(dpath)).isoformat()
                                })

        result = {
            "local_workflows": local_files,
            "scrapers": scrapers,
            "saved_data": saved_data,
            "remote_workflows_raw": remote_output or "(No active workflows found on remote or repository not pushed yet)"
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listing workflows: {e}"

@tool
def gh_list_runs(limit: int = 15, workflow: str = "", repo_dir: str = ".") -> str:
    """Lists recent GitHub Actions workflow runs, statuses (success, failure, in_progress, queued), durations, and URLs."""
    try:
        target = find_repo_root(resolve_path(repo_dir))
        cmd = ["gh", "run", "list", "--limit", str(limit), "--json", "databaseId,name,status,conclusion,createdAt,updatedAt,url,workflowName,workflowDatabaseId"]
        if workflow:
            cmd.extend(["--workflow", workflow])
        res = _run_git_cmd(cmd, cwd=target, timeout=15)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Error fetching GitHub Actions runs: {err}"
        return res.stdout.strip() or "[]"
    except Exception as e:
        return f"Error listing GitHub Actions runs: {e}"

@tool
def gh_trigger_workflow(workflow_name_or_file: str, repo_dir: str = ".") -> str:
    """Manually dispatches an on-demand run of a GitHub Actions workflow using 'gh workflow run'."""
    try:
        target = find_repo_root(resolve_path(repo_dir))
        wf = workflow_name_or_file.strip()
        cmd = ["gh", "workflow", "run", wf]
        res = _run_git_cmd(cmd, cwd=target, timeout=20)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Failed to trigger workflow '{wf}': {err}"
        return f"Successfully triggered workflow '{wf}'! Run started on GitHub Actions.\n{res.stdout.strip()}"
    except Exception as e:
        return f"Error triggering workflow '{workflow_name_or_file}': {e}"

@tool
def gh_get_run_logs(run_id: str, repo_dir: str = ".") -> str:
    """Fetches the full terminal execution logs of a specific GitHub Actions workflow run."""
    try:
        target = find_repo_root(resolve_path(repo_dir))
        clean_id = str(run_id).strip()
        cmd = ["gh", "run", "view", clean_id, "--log"]
        res = _run_git_cmd(cmd, cwd=target, timeout=25)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Failed to fetch logs for run #{clean_id}: {err}"
        logs = res.stdout.strip()
        lines = logs.splitlines()
        if len(lines) > 1500:
            return f"[Log truncated: showing last 1500 lines of {len(lines)}]\n" + "\n".join(lines[-1500:])
        return logs or "(Run has no logs yet or is currently queued)"
    except Exception as e:
        return f"Error fetching logs for run #{run_id}: {e}"

@tool
def gh_set_secret(secret_name: str, secret_value: str, repo_dir: str = ".") -> str:
    """Securely stores an encrypted secret in the GitHub repository (e.g. TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)."""
    try:
        target = find_repo_root(resolve_path(repo_dir))
        name = secret_name.strip().upper()
        val = secret_value.strip()
        if not name or not val:
            return "Error: secret_name and secret_value are both required."

        cmd = ["gh", "secret", "set", name, "--body", val]
        res = _run_git_cmd(cmd, cwd=target, timeout=15)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"Failed to set secret '{name}': {err}"
        return f"Successfully set encrypted secret '{name}' on GitHub repository."
    except Exception as e:
        return f"Error setting secret '{secret_name}': {e}"

@tool
def test_telegram_bot(bot_token: str, chat_id: str, message: str = "Test notification from John's Harness! 24/7 Cloud Scraper is working.") -> str:
    """Sends a test Telegram alert using the Telegram Bot API to verify bot credentials."""
    try:
        token = bot_token.strip()
        cid = chat_id.strip()
        if not token or not cid:
            return "Error: bot_token and chat_id are required."

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": cid,
            "text": message,
            "parse_mode": "Markdown"
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "JohnsHarness/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            if data.get("ok"):
                return f"Success! Telegram message sent to chat {cid}."
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='replace')
        return f"Telegram HTTP {e.code} Error: {err_msg}"
    except Exception as e:
        return f"Error contacting Telegram API: {e}"

@tool
def create_scraper_workflow(name: str, target_url: str, criteria: str = "", schedule_cron: str = "0 * * * *", telegram_notify: bool = True, repo_dir: str = ".") -> str:
    """Generates an end-to-end 24/7 cloud scraper script in 'scrapers/' and a matching scheduled GitHub Actions workflow in '.github/workflows/'."""
    try:
        ws = resolve_path(repo_dir)
        target = find_repo_root(ws)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
        if not safe_name:
            safe_name = "custom_scraper"

        # 1. Create directories in repo root (target)
        scrapers_dir = os.path.join(target, "scrapers")
        data_dir = os.path.join(scrapers_dir, "data")
        wf_dir = os.path.join(target, ".github", "workflows")
        os.makedirs(scrapers_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(wf_dir, exist_ok=True)

        if ws != target:
            try:
                os.makedirs(os.path.join(ws, "scrapers"), exist_ok=True)
                os.makedirs(os.path.join(ws, "scrapers", "data"), exist_ok=True)
            except Exception:
                pass

        # 2. Python scraper script template
        scraper_template = r'''#!/usr/bin/env python3
"""
Autonomous Cloud Scraper: __SAFE_NAME__
Target: __TARGET_URL__
Criteria: __CRITERIA__
Scheduled via GitHub Actions (Cron: __SCHEDULE_CRON__)
"""
import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime

TARGET_URL = "__TARGET_URL__"
CRITERIA = "__CRITERIA__"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "__SAFE_NAME___results.json")

def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[Telegram] Skipping notification: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "JohnsHarnessScraper/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("[Telegram] Notification sent successfully!")
            return True
    except Exception as e:
        print(f"[Telegram] Failed to send notification: {e}")
        return False

def run_scrape():
    print(f"[Scraper] Starting scrape for {TARGET_URL} at {datetime.now().isoformat()}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    req = urllib.request.Request(TARGET_URL, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Error] Failed to fetch {TARGET_URL}: {e}")
        sys.exit(1)

    print(f"[Scraper] Successfully downloaded {len(html)} bytes from {TARGET_URL}.")

    # Simple robust regex extraction for links and headings
    items = []
    matches = re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE)
    for href, text in matches:
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if clean_text and len(clean_text) > 8 and not href.startswith('#') and not href.startswith('javascript:'):
            full_url = urllib.parse.urljoin(TARGET_URL, href)
            if CRITERIA:
                keywords = [k.strip().lower() for k in CRITERIA.split() if len(k.strip()) > 2]
                if any(kw in clean_text.lower() for kw in keywords):
                    items.append({"title": clean_text, "url": full_url, "scraped_at": datetime.now().isoformat()})
            else:
                items.append({"title": clean_text, "url": full_url, "scraped_at": datetime.now().isoformat()})

    # Deduplicate by url
    unique_items = []
    seen = set()
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique_items.append(item)

    print(f"[Scraper] Found {len(unique_items)} matching items.")

    # Save to data directory
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_items, f, indent=2, ensure_ascii=False)
    print(f"[Scraper] Saved results to {DATA_FILE}.")

    # Telegram notification summary
    if unique_items:
        top_items = unique_items[:5]
        msg_lines = [
            f"🚀 *Scraper Alert: __SAFE_NAME__*",
            f"📍 *Source:* {TARGET_URL}",
            f"🎯 *Matched:* {len(unique_items)} items",
            ""
        ]
        for idx, itm in enumerate(top_items, 1):
            msg_lines.append(f"{idx}. [{itm['title']}]({itm['url']})")
        
        if len(unique_items) > 5:
            msg_lines.append(f"\\n_...and {len(unique_items) - 5} more items._")

        send_telegram("\\n".join(msg_lines))
    else:
        print("[Scraper] No items matched criteria on this run.")

if __name__ == "__main__":
    run_scrape()
'''
        scraper_code = (
            scraper_template
            .replace("__SAFE_NAME__", safe_name)
            .replace("__TARGET_URL__", target_url)
            .replace("__CRITERIA__", criteria or "Extract top items/updates")
            .replace("__SCHEDULE_CRON__", schedule_cron)
        )

        scraper_file = os.path.join(scrapers_dir, f"{safe_name}.py")
        with open(scraper_file, "w", encoding="utf-8") as f:
            f.write(scraper_code)

        if ws != target:
            try:
                with open(os.path.join(ws, "scrapers", f"{safe_name}.py"), "w", encoding="utf-8") as f:
                    f.write(scraper_code)
            except Exception:
                pass

        # 3. GitHub Actions workflow YAML
        wf_template = '''name: __NAME__ (24/7 Scraper)

on:
  schedule:
    - cron: '__SCHEDULE_CRON__'
  workflow_dispatch:

jobs:
  scrape_and_notify:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Run Scraper
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python scrapers/__SAFE_NAME__.py

      - name: Upload Scraped Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: __SAFE_NAME__-results
          path: scrapers/data/
          retention-days: 14
'''
        wf_yaml = (
            wf_template
            .replace("__NAME__", name)
            .replace("__SAFE_NAME__", safe_name)
            .replace("__SCHEDULE_CRON__", schedule_cron)
        )

        wf_file = os.path.join(wf_dir, f"{safe_name}.yml")
        with open(wf_file, "w", encoding="utf-8") as f:
            f.write(wf_yaml)

        return (
            f"Successfully created 24/7 scraper workflow '{safe_name}'!\n"
            f"- Scraper script: scrapers/{safe_name}.py\n"
            f"- GitHub Actions workflow: .github/workflows/{safe_name}.yml (Schedule: '{schedule_cron}')\n"
            f"- Output data target: scrapers/data/{safe_name}_results.json\n\n"
            f"Next steps:\n"
            f"1. Configure your Telegram bot credentials (TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID) via 'gh_set_secret' or the Dashboard.\n"
            f"2. Commit and push changes: call 'git_commit_and_push(commit_message=\"Add {safe_name} scraper workflow\")'.\n"
            f"3. GitHub Actions will run automatically on the cron schedule, or trigger immediately via 'gh_trigger_workflow(\"{safe_name}.yml\")'."
        )
    except Exception as e:
        return f"Error creating scraper workflow: {e}"

