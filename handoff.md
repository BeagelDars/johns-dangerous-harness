# Agent Handoff & Preferences

## User Communication Rules
- **Style:** Extremely concise, direct bullet points ("Claude save energy" style).
- **No fluff:** No long evaluations, no graphs/diagrams, no unsolicited filler.
- **Speed:** Quick summaries only.

## System Specs & Context
- **CPU:** AMD Ryzen 5 PRO 5650U (6 cores / 12 threads)
- **GPU:** AMD Radeon iGPU (512 MB VRAM, no CUDA, pure CPU inference)
- **RAM:** 16 GB total (~7.1 GB free)
- **Disk:** 360+ GB free on `C:\`
- **Python:** 3.12.10 installed

## Project Architecture & Current Files
- `harness/server.py`: Auto-detects if local model server is down; launches `ollama serve` completely silently with `CREATE_NO_WINDOW`.
- `harness/engine.py`: Agent loop with auto-server hookup, tool-calling, circuit breaker, trace events.
- `harness/registry.py`: `@tool` decorator, auto-generates schemas.
- `harness/tools.py`: Built-in tools (`run_powershell`, `calculate`, `run_python_code`, `read_file`, `write_file`, `list_directory`).
- `config.py`: Default cloud model `gemini-3.6-flash` with auto-fallback to `gemini-flash-lite-latest` and local `qwen2.5:3b`, system prompt.
- `main.py`: Interactive CLI runner.
- `launch_harness.bat`: Windows batch runner.
- `C:\Users\User\OneDrive\Desktop\Johns Harness.lnk`: Windows Desktop shortcut.

## Verification & Current State
- **Tools (35 registered):**
  - **Git Operations:** `git_status`, `git_diff`, `git_init`, `git_remote_add`, `git_commit_and_push`.
  - **File Operations:** `read_file`, `write_file`, `list_directory`, `read_file_range`, `replace_in_file`, `copy_file`, `move_file`, `delete_file` (with trash bin and root guards).
  - **Execution & Background:** `run_powershell`, `calculate`, `run_python_code`, `run_background_process`, `list_background_processes`, `check_background_process`, `stop_background_process`, `open_file`.
  - **Documents & Media:** `read_document`, `inspect_image`, `download_file`.
  - **Web & Research:** `web_search`, `fetch_webpage`.
  - **Workspace & Memory:** `save_memory`, `recall_memory`, `delete_memory`, `save_project_knowledge`, `get_workspace`, `set_workspace`, `create_project`.
- **Primary Model & Resilient Cascading Fallback:**
  - Primary: `gemini-3.6-flash`.
  - Auto-Fallback on 503 (High Demand / Unavailable), 500, 502, 504, 429, or thought_signature mismatch: Automatically demotes to `gemini-flash-lite-latest` without dropping the session.
  - Offline Fallback: If cloud is unreachable, falls back to `local` (`qwen2.5:3b`).
  - Alternative Provider Profiles: Added `groq` (`llama-3.3-70b-versatile`) and `openrouter` profiles in `config.py`.
- **Desktop Application (Electron):** Pure pitch-black (`#000000`) seamless Claude Code aesthetic (warm terracotta `#d97757` accents, zero emojis, zero clutter).
- **Left-Aligned Traces:** All tool calls (`Called <tool>`, etc.) and trace pills are strictly left-aligned with assistant message margins (`flex-direction: row`, `align-items: flex-start`, `text-align: left`).
- **Seamless Inline Trace:** Clean inline tool execution trace with subtle hairline timeline.
- **Auto-Collapsing Tool Trace:** Tool calls auto-fold into a compact line (`▶ Executed N tools`) upon completion, expandable on click.
- **Streaming Typewriter Response:** Responses stream in smoothly with live Markdown parsing.
- **Resizable Inspector Drawer:** Draggable left edge on the inspector panel allows custom width adjustment (260px to 85vw).
- **Executable & Shortcut:** Direct launch via Desktop shortcut `Johns Harness.lnk` targeting `dist\Johns Harness-win32-x64\Johns Harness.exe`.
