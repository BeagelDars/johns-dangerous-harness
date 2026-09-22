"""
Project & Session Storage Manager
Handles persistent project-scoped conversation sessions and global project registry
modeled after Claude Code and Antigravity best practices.
"""
import os
import json
import time
import uuid
import re
from typing import List, Dict, Any, Optional

REGISTRY_FILE = os.path.expanduser("~/.harness_projects.json")

def canonical_path(path: str) -> str:
    """Returns an absolute, normalized path. On Windows, normalizes drive letter and case for consistency."""
    if not path:
        return ""
    expanded = os.path.abspath(os.path.expanduser(str(path).strip().strip("'\"`")))
    norm = os.path.normpath(expanded)
    if os.name == "nt" and len(norm) >= 2 and norm[1] == ":":
        norm = norm[0].upper() + norm[1:]
    return norm

def paths_equal(p1: str, p2: str) -> bool:
    """Compares two paths canonicalized for the host operating system."""
    c1 = canonical_path(p1)
    c2 = canonical_path(p2)
    if os.name == "nt":
        return c1.lower() == c2.lower()
    return c1 == c2

def sanitize_session_id(session_id: str) -> str:
    """Sanitizes session ID to prevent path traversal and invalid characters."""
    if not session_id:
        return f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '', str(session_id))
    return clean if clean else f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"

def _load_registry() -> Dict[str, Any]:
    if not os.path.exists(REGISTRY_FILE):
        return {"projects": []}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"projects": []}
            # Deduplicate existing projects in registry
            raw_projects = data.get("projects", [])
            seen = set()
            deduped = []
            for p in raw_projects:
                if not isinstance(p, dict):
                    continue
                p_path = canonical_path(p.get("path", ""))
                if not p_path:
                    continue
                k = p_path.lower() if os.name == "nt" else p_path
                if k not in seen:
                    seen.add(k)
                    p["path"] = p_path
                    deduped.append(p)
            data["projects"] = deduped
            return data
    except Exception:
        return {"projects": []}

def _save_registry(data: Dict[str, Any]):
    try:
        tmp_file = f"{REGISTRY_FILE}.{uuid.uuid4().hex[:6]}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, REGISTRY_FILE)
    except Exception:
        if 'tmp_file' in locals() and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass

def register_project(project_path: str) -> Dict[str, Any]:
    """Registers a project path in the global project registry and initializes .harness/."""
    abs_path = canonical_path(project_path)
    if not abs_path:
        return {"path": "", "name": ""}

    name = os.path.basename(abs_path) or abs_path

    # Ensure .harness/sessions directory exists
    harness_dir = os.path.join(abs_path, ".harness")
    sessions_dir = os.path.join(harness_dir, "sessions")
    try:
        os.makedirs(sessions_dir, exist_ok=True)
    except Exception:
        pass

    data = _load_registry()
    projects = data.get("projects", [])

    # Find or update project with case-insensitive matching
    found = None
    for p in projects:
        if paths_equal(p.get("path", ""), abs_path):
            found = p
            p["last_active"] = time.time()
            p["name"] = name
            p["path"] = abs_path
            break

    if not found:
        project_obj = {
            "path": abs_path,
            "name": name,
            "created_at": time.time(),
            "last_active": time.time()
        }
        projects.insert(0, project_obj)
    else:
        # Update existing project attributes without jumping position in sidebar list
        found["last_active"] = time.time()
        found["name"] = name
        found["path"] = abs_path

    data["projects"] = projects[:50]  # Keep recent 50 projects
    _save_registry(data)
    return {"path": abs_path, "name": name}

def unregister_project(project_path: str) -> bool:
    """Removes a project from the global project registry."""
    abs_path = canonical_path(project_path)
    data = _load_registry()
    projects = data.get("projects", [])
    initial_len = len(projects)
    filtered = [p for p in projects if not paths_equal(p.get("path", ""), abs_path)]
    if len(filtered) != initial_len:
        data["projects"] = filtered
        _save_registry(data)
        return True
    return False

def list_projects() -> List[Dict[str, Any]]:
    """Returns all registered projects that still exist on disk, with their session summaries."""
    data = _load_registry()
    projects = data.get("projects", [])
    result = []
    seen = set()

    for p in projects:
        path = p.get("path")
        if not path:
            continue
        c_path = canonical_path(path)
        norm_key = c_path.lower() if os.name == "nt" else c_path
        if norm_key in seen:
            continue
        seen.add(norm_key)

        if os.path.exists(c_path):
            sessions = list_sessions(c_path)
            result.append({
                "path": c_path,
                "name": p.get("name") or os.path.basename(c_path) or c_path,
                "last_active": p.get("last_active", 0),
                "sessions": sessions
            })

    return result

def get_sessions_dir(project_path: str) -> str:
    abs_path = canonical_path(project_path)
    sessions_dir = os.path.join(abs_path, ".harness", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    return sessions_dir

def list_sessions(project_path: str) -> List[Dict[str, Any]]:
    """Returns list of sessions for a given project sorted newest first. Tolerant of corrupt files."""
    try:
        sessions_dir = get_sessions_dir(project_path)
    except Exception:
        return []

    if not os.path.exists(sessions_dir):
        return []

    sessions = []
    try:
        for fname in os.listdir(sessions_dir):
            if fname.endswith(".json") and not fname.endswith(".tmp"):
                fpath = os.path.join(sessions_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        if isinstance(meta, dict):
                            s_id = meta.get("id") or os.path.splitext(fname)[0]
                            sessions.append({
                                "id": s_id,
                                "title": meta.get("title", "Conversation"),
                                "created_at": meta.get("created_at", 0),
                                "updated_at": meta.get("updated_at", meta.get("created_at", 0)),
                                "message_count": len(meta.get("messages", []))
                            })
                except Exception:
                    continue
    except Exception:
        return []

    sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
    return sessions

def load_session(project_path: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Loads a full session transcript safely."""
    try:
        sessions_dir = get_sessions_dir(project_path)
    except Exception:
        return None

    safe_id = sanitize_session_id(session_id)
    fpath = os.path.join(sessions_dir, f"{safe_id}.json")
    if not os.path.exists(fpath):
        return None
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None
    except Exception:
        return None

def save_session(
    project_path: str,
    session_id: str,
    title: str,
    messages: List[Dict[str, Any]],
    model: str = "",
    mode: str = ""
) -> bool:
    """Atomically saves session transcript to project's .harness/sessions/."""
    try:
        sessions_dir = get_sessions_dir(project_path)
    except Exception:
        return False

    safe_id = sanitize_session_id(session_id)
    fpath = os.path.join(sessions_dir, f"{safe_id}.json")

    now = time.time()
    existing = load_session(project_path, safe_id)
    created_at = existing.get("created_at", now) if existing else now

    clean_title = (title or "Conversation").strip()
    if "\n" in clean_title:
        clean_title = clean_title.split("\n")[0].strip()
    if len(clean_title) > 60:
        clean_title = clean_title[:57] + "..."

    payload = {
        "id": safe_id,
        "title": clean_title,
        "created_at": created_at,
        "updated_at": now,
        "workspace": canonical_path(project_path),
        "model": model or (existing.get("model", "") if existing else ""),
        "mode": mode or (existing.get("mode", "") if existing else ""),
        "message_count": len(messages),
        "messages": messages
    }

    tmp_path = os.path.join(sessions_dir, f".{safe_id}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, fpath)
        return True
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False

def rename_session(project_path: str, session_id: str, new_title: str) -> bool:
    """Renames an existing session."""
    data = load_session(project_path, session_id)
    if not data:
        return False
    clean_title = new_title.strip() if new_title else "Conversation"
    return save_session(
        project_path=project_path,
        session_id=session_id,
        title=clean_title,
        messages=data.get("messages", []),
        model=data.get("model", ""),
        mode=data.get("mode", "")
    )

def delete_session(project_path: str, session_id: str) -> bool:
    """Deletes a session transcript safely."""
    try:
        sessions_dir = get_sessions_dir(project_path)
    except Exception:
        return False

    safe_id = sanitize_session_id(session_id)
    fpath = os.path.join(sessions_dir, f"{safe_id}.json")
    deleted = False
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            deleted = True
        except Exception:
            deleted = False

    # Also clean up any lingering temporary files for this session
    try:
        for fname in os.listdir(sessions_dir):
            if fname.startswith(f".{safe_id}.") and fname.endswith(".tmp"):
                try:
                    os.remove(os.path.join(sessions_dir, fname))
                except Exception:
                    pass
    except Exception:
        pass

    return deleted
