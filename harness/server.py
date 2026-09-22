"""
Server Manager: Automatically and silently starts the local Ollama server if it is not running.
"""
import os
import sys
import time
import shutil
import urllib.request
import subprocess

OLLAMA_CHECK_URL = "http://localhost:11434/api/tags"

def is_server_running() -> bool:
    """Checks if the local Ollama server is responding."""
    try:
        with urllib.request.urlopen(OLLAMA_CHECK_URL, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def find_ollama_executable() -> str:
    """Finds the ollama binary on the system."""
    found = shutil.which("ollama")
    if found:
        return found

    # Fallback to standard Windows install directory
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    standard_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
    if os.path.exists(standard_path):
        return standard_path

    program_files = os.environ.get("ProgramFiles", "")
    pf_path = os.path.join(program_files, "Ollama", "ollama.exe")
    if os.path.exists(pf_path):
        return pf_path

    return "ollama"

def ensure_server_running(timeout: int = 10) -> bool:
    """Ensures Ollama is running silently. Starts it in the background if down."""
    if is_server_running():
        return True

    ollama_bin = find_ollama_executable()
    print("  [Auto-Server] Local model server is offline. Starting silently in background...")

    # Windows flag to start completely hidden with no console popup
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    try:
        subprocess.Popen(
            [ollama_bin, "serve"],
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"  [Auto-Server Error] Failed to launch '{ollama_bin}': {e}")
        return False

    # Wait until the server answers
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(0.5)
        if is_server_running():
            print("  [Auto-Server] Server connected and ready! [OK]")
            return True

    print("  [Auto-Server Warning] Server started but did not respond within timeout.")
    return False
