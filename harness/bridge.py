"""
Headless JSON-RPC / Stdio Protocol Bridge for Electron.
Communicates via newline-delimited JSON messages over stdin and stdout.
Coordinates workspace state, project registration, session persistence,
and agent execution stream with robust error recovery.
"""
import sys
import os
import json
import threading
from typing import Any, Optional, List, Dict

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

from harness.engine import AgentEngine
from harness.registry import registry
from harness.memory import load_memories
from harness import tools
from harness import session
import config

_emit_lock = threading.Lock()

def emit(event: dict):
    """Writes a JSON event to stdout followed by a newline."""
    try:
        line = json.dumps(event, ensure_ascii=False)
        with _emit_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    except Exception:
        pass

current_worker = None
worker_lock = threading.Lock()

def query_worker(agent: AgentEngine, query_text: str, attachments: Any, req_id: int):
    try:
        stream = agent.run(query_text, attachments=attachments)
        for event in stream:
            if agent.aborted:
                break
            event_copy = dict(event)
            event_copy["req_id"] = req_id
            if "id" not in event_copy or not event_copy["id"]:
                event_copy["id"] = req_id
            emit(event_copy)
        if agent.aborted:
            emit({"id": req_id, "req_id": req_id, "type": "aborted", "content": "[Generation stopped by user]"})
        emit({"id": req_id, "req_id": req_id, "type": "done"})
    except Exception as e:
        if not agent.aborted:
            emit({"id": req_id, "req_id": req_id, "type": "error", "error": str(e)})
        emit({"id": req_id, "req_id": req_id, "type": "done"})

def main():
    global current_worker
    agent = AgentEngine()

    # Initial workspace registration
    current_ws = tools.get_active_workspace()
    session.register_project(current_ws)

    # Auto-notify Electron whenever workspace changes (even from agent tools like set_workspace/create_project)
    def on_workspace_changed(new_path: str):
        emit({
            "type": "workspace_changed",
            "path": new_path,
            "name": os.path.basename(new_path) or new_path,
            "source": "tool",
            "projects": session.list_projects(),
            "sessions": session.list_sessions(new_path)
        })

    tools.add_workspace_listener(on_workspace_changed)

    def on_tasks_changed():
        emit({
            "type": "tasks_updated",
            "tasks": tools.get_background_tasks()
        })

    tools.add_background_listener(on_tasks_changed)

    # Periodic background monitor for active process uptime and auto-exit detection
    def tasks_monitor_loop():
        import time
        last_count = 0
        while True:
            time.sleep(2.0)
            try:
                tasks = tools.get_background_tasks()
                if tasks or last_count > 0:
                    emit({
                        "type": "tasks_updated",
                        "tasks": tasks
                    })
                last_count = len(tasks)
            except Exception:
                pass

    monitor_thread = threading.Thread(target=tasks_monitor_loop, daemon=True)
    monitor_thread.start()

    # Initial ready handshake
    emit({
        "type": "ready",
        "model": agent.model,
        "mode": agent.active_mode,
        "max_steps": agent.max_steps,
        "tools_count": len(registry.get_schemas()),
        "workspace": current_ws,
        "workspace_name": os.path.basename(current_ws) or current_ws,
        "projects": session.list_projects(),
        "sessions": session.list_sessions(current_ws),
        "memories": load_memories(),
        "tasks": tools.get_background_tasks()
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            emit({"type": "error", "error": f"Invalid JSON: {e}"})
            continue

        action = cmd.get("action")
        req_id = cmd.get("id", 0)

        if action == "ping":
            emit({"id": req_id, "type": "pong"})

        elif action == "get_status":
            ws = tools.get_active_workspace()
            emit({
                "id": req_id,
                "type": "status",
                "model": agent.model,
                "mode": agent.active_mode,
                "max_steps": agent.max_steps,
                "tools_count": len(registry.get_schemas()),
                "workspace": ws,
                "workspace_name": os.path.basename(ws) or ws,
                "projects": session.list_projects(),
                "sessions": session.list_sessions(ws),
                "memories": load_memories(),
                "tasks": tools.get_background_tasks()
            })

        elif action == "list_projects":
            emit({
                "id": req_id,
                "type": "projects_list",
                "projects": session.list_projects()
            })

        elif action == "unregister_project":
            raw_path = cmd.get("path", "")
            ok = session.unregister_project(raw_path)
            emit({
                "id": req_id,
                "type": "project_unregistered",
                "success": ok,
                "path": raw_path,
                "projects": session.list_projects()
            })

        elif action == "list_sessions":
            proj_path = cmd.get("path") or tools.get_active_workspace()
            emit({
                "id": req_id,
                "type": "sessions_list",
                "path": session.canonical_path(proj_path),
                "sessions": session.list_sessions(proj_path)
            })

        elif action == "load_session":
            proj_path = cmd.get("path") or tools.get_active_workspace()
            s_id = cmd.get("session_id", "")

            # Abort any active query before loading another session
            with worker_lock:
                if current_worker and current_worker.is_alive():
                    agent.abort()
                    current_worker.join(timeout=1.0)

            # Synchronize active workspace to the project containing this session
            try:
                tools.set_active_workspace(proj_path)
            except Exception:
                pass

            sess_data = session.load_session(proj_path, s_id)
            if sess_data:
                # Reconstruct agent memory with grounded system prompt
                agent.history = []
                current_sys = config.get_system_prompt()
                agent.history.append({"role": "system", "content": current_sys})

                for msg in sess_data.get("messages", []):
                    r = msg.get("role")
                    content = msg.get("content", "")
                    if r == "user":
                        agent.history.append({"role": "user", "content": content})
                    elif r in ("assistant", "agent"):
                        agent.history.append({"role": "assistant", "content": content or "[Executed actions]"})

                emit({
                    "id": req_id,
                    "type": "session_loaded",
                    "path": session.canonical_path(proj_path),
                    "session": sess_data
                })
            else:
                emit({"id": req_id, "type": "error", "error": f"Session {s_id} not found in {proj_path}"})

        elif action == "save_session":
            proj_path = cmd.get("path") or tools.get_active_workspace()
            s_id = cmd.get("session_id", "")
            title = cmd.get("title", "Conversation")
            messages = cmd.get("messages", [])
            model = cmd.get("model", agent.model)
            mode = cmd.get("mode", agent.active_mode)

            ok = session.save_session(
                project_path=proj_path,
                session_id=s_id,
                title=title,
                messages=messages,
                model=model,
                mode=mode
            )
            emit({
                "id": req_id,
                "type": "session_saved",
                "success": ok,
                "path": session.canonical_path(proj_path),
                "session_id": s_id,
                "sessions": session.list_sessions(proj_path)
            })

        elif action == "rename_session":
            proj_path = cmd.get("path") or tools.get_active_workspace()
            s_id = cmd.get("session_id", "")
            new_title = cmd.get("title", "").strip()

            ok = session.rename_session(proj_path, s_id, new_title)
            emit({
                "id": req_id,
                "type": "session_renamed",
                "success": ok,
                "path": session.canonical_path(proj_path),
                "session_id": s_id,
                "title": new_title,
                "sessions": session.list_sessions(proj_path)
            })

        elif action == "delete_session":
            proj_path = cmd.get("path") or tools.get_active_workspace()
            s_id = cmd.get("session_id", "")
            ok = session.delete_session(proj_path, s_id)
            emit({
                "id": req_id,
                "type": "session_deleted",
                "success": ok,
                "path": session.canonical_path(proj_path),
                "session_id": s_id,
                "sessions": session.list_sessions(proj_path)
            })

        elif action == "set_workspace":
            raw_path = cmd.get("path", "")
            try:
                new_ws = tools.set_active_workspace(raw_path)
                emit({
                    "id": req_id,
                    "type": "workspace_changed",
                    "path": new_ws,
                    "name": os.path.basename(new_ws) or new_ws,
                    "source": "user",
                    "projects": session.list_projects(),
                    "sessions": session.list_sessions(new_ws)
                })
            except Exception as e:
                emit({"id": req_id, "type": "error", "error": f"Failed to switch workspace: {e}"})

        elif action == "switch_profile":
            profile = cmd.get("profile", "auto")
            ok = agent.switch_profile(profile)
            emit({
                "id": req_id,
                "type": "switched",
                "success": ok,
                "mode": agent.active_mode,
                "model": agent.model,
                "base_url": agent.base_url
            })

        elif action == "set_steps":
            steps = cmd.get("steps", 25)
            if isinstance(steps, int) and steps > 0:
                agent.max_steps = steps
            emit({"id": req_id, "type": "steps_updated", "max_steps": agent.max_steps})

        elif action == "clear":
            with worker_lock:
                if current_worker and current_worker.is_alive():
                    agent.abort()
                    current_worker.join(timeout=1.0)
            agent.history = []
            emit({"id": req_id, "type": "cleared"})

        elif action == "abort":
            agent.abort()
            emit({"id": req_id, "type": "aborted", "content": "[Generation stopped by user]"})
            emit({"id": req_id, "type": "done"})

        elif action == "query":
            query_text = cmd.get("text", "").strip()
            attachments = cmd.get("attachments", [])
            if not query_text and not attachments:
                emit({"id": req_id, "type": "done", "content": ""})
                continue

            with worker_lock:
                if current_worker and current_worker.is_alive():
                    agent.abort()
                    current_worker.join(timeout=1.0)

                agent.aborted = False
                current_worker = threading.Thread(
                    target=query_worker,
                    args=(agent, query_text, attachments, req_id),
                    daemon=True
                )
                current_worker.start()

        elif action == "get_background_tasks":
            emit({
                "id": req_id,
                "type": "tasks_updated",
                "tasks": tools.get_background_tasks()
            })

        elif action == "stop_process":
            raw_pid = cmd.get("pid")
            res = tools.stop_background_process(raw_pid, terminated_by_user=True)
            emit({
                "id": req_id,
                "type": "tasks_updated",
                "tasks": tools.get_background_tasks(),
                "message": res
            })

        elif action == "get_process_output":
            raw_pid = cmd.get("pid")
            try:
                pid_int = int(raw_pid)
            except Exception:
                pid_int = 0
            out = tools.get_background_task_output(pid_int)
            emit({
                "id": req_id,
                "type": "process_output",
                "pid": raw_pid,
                "output": out
            })

        elif action == "exit":
            agent.abort()
            break

if __name__ == "__main__":
    main()
