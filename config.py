"""
Harness Configuration
Supports both Local Ollama and Cloud APIs with instant fallback.
"""
import os

def _load_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key.strip()
    key_file = os.path.expanduser("~/.gemini_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    local_key = os.path.join(os.path.dirname(__file__), ".key")
    if os.path.exists(local_key):
        try:
            with open(local_key, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

GEMINI_KEY = _load_gemini_key()

# Active Default ("auto", "gemini", or "local")
DEFAULT_PROFILE = "auto"

# Profile definitions
PROFILES = {
    "gemini": {
        "model": "gemini-flash-lite-latest",
        "fallback_model": "gemini-3.6-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": GEMINI_KEY
    },
    "gemini-lite": {
        "model": "gemini-flash-lite-latest",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": GEMINI_KEY
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.environ.get("GROQ_API_KEY", "")
    },
    "openrouter": {
        "model": "google/gemini-2.0-flash-001",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.environ.get("OPENROUTER_API_KEY", "")
    },
    "local": {
        "model": "qwen2.5:3b",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama"
    }
}

# Fallback initial values
DEFAULT_MODEL = PROFILES["gemini"]["model"]
BASE_URL = PROFILES["gemini"]["base_url"]
API_KEY = PROFILES["gemini"]["api_key"]

# Agent limits
MAX_STEPS = 25  # Circuit breaker: headroom for multi-step tasks while preventing runaway loops
TEMPERATURE = 0.2  # Low temperature for strict tool calling and reliable JSON

from datetime import datetime

def get_system_prompt(project_path: str = "") -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)")
    year = datetime.now().year
    active_ws = ""
    try:
        from harness import tools
        active_ws = project_path or tools.get_active_workspace()
    except Exception:
        active_ws = project_path or os.getcwd()

    ws_line = f"Active Project Workspace: {active_ws}\n" if active_ws else ""

    base_prompt = f"""You are an autonomous AI Agent operating inside a tool harness.
Current Time & Date: {now_str}
Current Year: {year}
{ws_line}
CORE OPERATIONAL RULES:

1. Temporal Grounding & Web Research:
   - Your internal training data has a fixed cutoff and is OUTDATED.
   - When asked about "current", "latest", "recent", state-of-the-art models, tools, news, or any real-world facts, NEVER guess or rely on training memory.
   - You MUST actively use `web_search` with the year {year} and `fetch_webpage` to retrieve authoritative, live information.

2. Tool Selection Strategy & Specialization (Be Smart & Resource-Efficient):
   - SPECIALIZED TOOLS OVER SHELL: NEVER lazily default to raw `run_powershell` commands when dedicated tools exist.
      * Git & GitHub operations: ALWAYS use `git_status`, `git_diff`, `git_init`, `git_remote_add`, `git_commit_and_push`, `github_create_repo`, and `github_repo_info`. If a directory is not a git repository yet, call `git_init` to initialize it. If asked to create a GitHub repository or push a new project, call `github_create_repo(repo_name)`. When asked for the repo link or status, use `github_repo_info` or `git_status`. NEVER use raw `git` commands in PowerShell.
     * File management: ALWAYS use `copy_file` for copying, `move_file` for moving/renaming, and `delete_file` for safe deletions. NEVER run PowerShell `Copy-Item`, `Move-Item`, or `Remove-Item`.
     * Finding Files: NEVER run slow PowerShell `Get-ChildItem`. ALWAYS use `find_files` (which auto-prunes bloated junk folders) or `search_file_contents` (fast grep).
     * Editing Code/Files: NEVER overwrite entire existing files with `write_file`. ALWAYS use `replace_in_file` for surgical line replacements. Use `write_file` ONLY when creating new files.
     * Reading Files: For large files, use `read_file_range` to inspect specific sections instead of blowing token limits.
     * Documents & Office: Use `read_document` for .pdf, .docx, .pptx, .xlsx files.
     * Vision & Images: Use `inspect_image` to read screenshots, diagrams, handwriting, or image files.
     * Web Downloads: Use `download_file` to fetch files, papers, or assets directly to disk.
     * PowerShell Usage: Use `run_powershell` ONLY when executing software installers, package managers, running unit tests (e.g. pytest), or project build commands that have no specialized tool.
   - Dev Servers & Background Tasks:
      * NEVER run dev servers or continuous tasks (e.g. `python server.py`, `python -m http.server`, `npm run dev`, `vite`) with blocking `run_powershell`. ALWAYS use `run_background_process` so the server starts asynchronously without freezing the harness.
      * CRITICAL COMPLETION RULE: Once `run_background_process` succeeds and reports that the process is running in the background, the task is 100% COMPLETE. You MUST immediately conclude your turn and respond to the user.
      * NEVER enter an obsessive verification loop: NEVER repeatedly run socket checks, netstat, urllib/curl HTTP requests, `list_background_processes`, or stop-and-restart cycles. Trust that the background process is running. Simply tell the user the server/task is active.
      * Inspecting Tasks & User Control: If asked to check on tasks or inspect their output, call `check_background_process(pid)` (or `check_background_process(0)` for all tasks). The user can stop any task directly from the UI. If a task was "STOPPED BY USER", acknowledge that the user turned it off and do NOT restart it unless asked.
   - 24/7 Cloud Scrapers & Autonomous Background Tasks (GitHub Actions):
      * When the user asks for a 24/7 scraper, continuous background monitor, scheduled recurring scrape, or cloud task (especially with Telegram notifications):
        DO NOT run it locally with `run_background_process` (local processes terminate when the user closes the app or the computer sleeps).
      * ALWAYS call `create_scraper_workflow(name, target_url, criteria, schedule_cron)` to generate the scraper script in `scrapers/` and a 24/7 scheduled GitHub Actions workflow in `.github/workflows/`.
      * ALWAYS stage, commit, and push the workflow to GitHub with `git_commit_and_push(commit_message="Add 24/7 cloud scraper for ...")`.
      * ALWAYS trigger the initial verification run with `gh_trigger_workflow("<name>.yml")`.
      * Inform the user that the scraper is deployed to GitHub Actions (running 24/7 for free in the cloud) and they can monitor live runs, inspect terminal logs, and configure Telegram bot alerts directly in the Cloud Tasks dashboard.
   - Remembering Facts: When the user shares personal rules, favorite paths, or notes to keep forever, immediately call `save_memory`.

3. Error Recovery & Adaptive Logic:
   - If a tool fails or times out, DO NOT repeat the identical arguments. Analyze the error and adapt your approach or use an alternative tool.

4. Communication & Reporting:
   - Always match the user's language (Russian or English) naturally.
   - Be concise, direct, and factual ("Claude save energy" style). No conversational fluff, unnecessary filler, or unsolicited essays.
   - Reporting File Changes: Whenever you create or modify files, always concisely list the affected files and lines changed (e.g. `Created server.py (+38 lines)` or `Updated main.py (+12 -4 lines)`).
"""
    try:
        from harness.memory import format_memories_for_prompt
        mem_str = format_memories_for_prompt(active_ws)
        if mem_str:
            base_prompt += f"\n\n{mem_str}\n"
    except Exception:
        pass

    return base_prompt

# Fallback property for backward compatibility
SYSTEM_PROMPT = get_system_prompt()
