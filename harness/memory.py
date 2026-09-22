"""
Persistent Memory Store for the Agent Harness.
Saves memories to ~/.harness_memory.json so they persist across
process kills, reboot, project changes, and new sessions.
Also manages project-scoped knowledge in .harness/knowledge.json.
"""
import os
import json
import uuid
from datetime import datetime
from harness.session import canonical_path

MEMORY_FILE = os.path.expanduser("~/.harness_memory.json")

def load_memories() -> dict:
    """Loads all memories from the persistent store."""
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_memory_entry(key: str, value: str) -> None:
    """Saves or updates a memory entry permanently and atomically."""
    memories = load_memories()
    memories[key.strip()] = {
        "value": value.strip(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    tmp_file = f"{MEMORY_FILE}.{uuid.uuid4().hex[:6]}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, MEMORY_FILE)
    except Exception:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        raise

def delete_memory_entry(key: str) -> bool:
    """Deletes a memory key permanently."""
    memories = load_memories()
    clean_key = key.strip()
    if clean_key in memories:
        del memories[clean_key]
        tmp_file = f"{MEMORY_FILE}.{uuid.uuid4().hex[:6]}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, MEMORY_FILE)
            return True
        except Exception:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            return False
    return False

def get_project_knowledge_file(project_path: str = "", create_dir: bool = False) -> str:
    from harness import tools
    p = project_path or getattr(tools, "ACTIVE_WORKSPACE", os.getcwd())
    abs_p = canonical_path(p)
    harness_dir = os.path.join(abs_p, ".harness")
    if create_dir:
        os.makedirs(harness_dir, exist_ok=True)
    return os.path.join(harness_dir, "knowledge.json")

def load_project_knowledge(project_path: str = "") -> dict:
    """Loads project-specific knowledge from .harness/knowledge.json."""
    kf = get_project_knowledge_file(project_path, create_dir=False)
    if not os.path.exists(kf):
        return {}
    try:
        with open(kf, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_project_knowledge(key: str, value: str, project_path: str = "") -> None:
    """Saves a project-specific knowledge entry to .harness/knowledge.json atomically."""
    knowledge = load_project_knowledge(project_path)
    knowledge[key.strip()] = {
        "value": value.strip(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    kf = get_project_knowledge_file(project_path, create_dir=True)
    tmp_file = f"{kf}.{uuid.uuid4().hex[:6]}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(knowledge, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, kf)
    except Exception:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        raise

def format_memories_for_prompt(project_path: str = "") -> str:
    """Formats all saved global memories and project knowledge for the system prompt."""
    memories = load_memories()
    proj_knowledge = load_project_knowledge(project_path)

    sections = []
    if memories:
        lines = ["GLOBAL MEMORY & PREFERENCES (Active across all projects):"]
        for k, v in memories.items():
            val = v.get("value", "") if isinstance(v, dict) else str(v)
            lines.append(f"- [{k}]: {val}")
        sections.append("\n".join(lines))

    if proj_knowledge:
        lines = ["PROJECT-SPECIFIC KNOWLEDGE (.harness/knowledge.json):"]
        for k, v in proj_knowledge.items():
            val = v.get("value", "") if isinstance(v, dict) else str(v)
            lines.append(f"- [{k}]: {val}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
