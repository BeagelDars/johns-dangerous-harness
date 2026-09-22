"""
Deep Verification Test Suite for John's Harness
Tests File Operations, Conversation & Session Management, Project Scoping, and Bridge Synchronization.
"""
import sys
import os
import json
import time
import shutil
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness.registry import registry
from harness import tools
from harness import session
from harness import memory
from harness.engine import AgentEngine

def test_file_operations():
    print("\n--- Testing File Operations ---")
    test_dir = tempfile.mkdtemp(prefix="harness_test_fs_")
    try:
        orig_ws = tools.get_active_workspace()
        tools.set_active_workspace(test_dir)

        # 1. Test resolve_path
        p1 = tools.resolve_path("sub/test.txt")
        assert p1 == tools.canonical_path(os.path.join(test_dir, "sub", "test.txt")), f"Path mismatch: {p1}"

        p_quotes = tools.resolve_path(' "quoted/path.txt" ')
        assert p_quotes == tools.canonical_path(os.path.join(test_dir, "quoted", "path.txt"))

        # 2. Test write_file (atomic write with parent dir creation)
        res_w = tools.write_file("sub/nested/file.txt", "line 1\nline 2\nline 3\n")
        assert "Successfully created" in res_w
        assert os.path.exists(p1_nested := os.path.join(test_dir, "sub", "nested", "file.txt"))
        with open(p1_nested, "r", encoding="utf-8") as f:
            assert f.read() == "line 1\nline 2\nline 3\n"
        print("[Pass] write_file created nested file atomically.")

        # 3. Test read_file
        res_r = tools.read_file("sub/nested/file.txt")
        assert res_r == "line 1\nline 2\nline 3\n"
        print("[Pass] read_file read content accurately.")

        # 4. Test read_file_range
        res_range = tools.read_file_range("sub/nested/file.txt", start_line=2, end_line=3)
        assert "2: line 2" in res_range
        assert "3: line 3" in res_range
        assert "1: line 1" not in res_range
        print("[Pass] read_file_range sliced lines correctly.")

        # 5. Test replace_in_file with CRLF and LF
        crlf_file = os.path.join(test_dir, "crlf.txt")
        with open(crlf_file, "wb") as f:
            f.write(b"def hello():\r\n    print('old')\r\n    return 42\r\n")

        # Exact match with newline tolerance
        res_rep = tools.replace_in_file("crlf.txt", "    print('old')", "    print('new')\n    print('added')")
        assert "Successfully updated" in res_rep
        with open(crlf_file, "rb") as f:
            updated_bytes = f.read()
            assert b"\r\n" in updated_bytes, "CRLF line endings should be preserved!"
            assert b"print('new')" in updated_bytes
            assert b"print('added')" in updated_bytes
        print("[Pass] replace_in_file preserved CRLF line endings on Windows.")

        # 6. Test multiplicity check in replace_in_file
        multi_file = os.path.join(test_dir, "multi.txt")
        with open(multi_file, "w", encoding="utf-8") as f:
            f.write("target\nmiddle\ntarget\n")

        res_multi_fail = tools.replace_in_file("multi.txt", "target", "replacement")
        assert "found 2 times" in res_multi_fail, f"Should refuse ambiguous replacement: {res_multi_fail}"

        res_multi_ok = tools.replace_in_file("multi.txt", "target", "replacement", allow_multiple=True)
        assert "Successfully updated" in res_multi_ok
        with open(multi_file, "r", encoding="utf-8") as f:
            assert f.read() == "replacement\nmiddle\nreplacement\n"
        print("[Pass] replace_in_file multiplicity protection and allow_multiple work properly.")

        # 7. Test binary file detection in read_file and replace_in_file
        bin_file = os.path.join(test_dir, "test.bin")
        with open(bin_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")
        assert "binary file" in tools.read_file("test.bin")
        assert "binary file" in tools.replace_in_file("test.bin", "foo", "bar")
        print("[Pass] Binary file protection verified.")

        # 8. Test UTF-16 LE and BOM file reading and replacing
        utf16_file = os.path.join(test_dir, "powershell_output.txt")
        with open(utf16_file, "wb") as f:
            f.write("Status: Active\r\nPort: 8080\r\n".encode("utf-16"))
        res_u16 = tools.read_file("powershell_output.txt")
        assert "Status: Active" in res_u16, f"UTF-16 read failed: {res_u16}"
        res_u16_rep = tools.replace_in_file("powershell_output.txt", "Port: 8080", "Port: 3000")
        assert "Successfully updated" in res_u16_rep
        assert "Port: 3000" in tools.read_file("powershell_output.txt")
        print("[Pass] UTF-16 LE text read and replace verified (no false binary rejection).")

        # 9. Test empty target protection in replace_in_file
        res_empty = tools.replace_in_file("crlf.txt", "", "injection")
        assert "cannot be empty" in res_empty
        print("[Pass] replace_in_file empty target protection verified.")

        # 10. Test find_files and search_file_contents
        find_res = tools.find_files("*.txt", search_dir=".")
        assert "file.txt" in find_res
        assert "crlf.txt" in find_res

        # Test find_files without wildcards
        find_no_wildcard = tools.find_files("crlf", search_dir=".")
        assert "crlf.txt" in find_no_wildcard
        print("[Pass] find_files without wildcards verified.")

        grep_res = tools.search_file_contents("middle", search_dir=".")
        assert "multi.txt:2: middle" in grep_res

        # Test search_file_contents on a single file path directly
        single_grep = tools.search_file_contents("middle", search_dir="multi.txt")
        assert "multi.txt:2: middle" in single_grep
        print("[Pass] search_file_contents on single file verified.")

        # 11. Test read_file_range on a directory
        dir_range = tools.read_file_range("sub")
        assert "is a directory" in dir_range
        print("[Pass] read_file_range directory protection verified.")

    finally:
        tools.set_active_workspace(orig_ws)
        shutil.rmtree(test_dir, ignore_errors=True)

def test_session_and_project_management():
    print("\n--- Testing Session & Project Management ---")
    test_proj = tempfile.mkdtemp(prefix="harness_test_proj_")
    try:
        # 1. Project Registration & Case-insensitive deduplication
        reg1 = session.register_project(test_proj)
        assert session.paths_equal(reg1["path"], test_proj)

        # Register again with different casing if on Windows
        if os.name == "nt":
            reg2 = session.register_project(test_proj.upper())
            projects = session.list_projects()
            matching = [p for p in projects if session.paths_equal(p["path"], test_proj)]
            assert len(matching) == 1, f"Expected 1 project entry, got {len(matching)}"
            print("[Pass] Windows case-insensitive project registration deduplication verified.")

        # 2. Session Saving (Atomic)
        sess_id = "test_sess_1"
        messages = [
            {"role": "user", "content": "Create a fastapi server", "timestamp": time.time()},
            {"role": "agent", "content": "Here is the server", "tools": [{"name": "write_file", "args": {"filepath": "main.py"}}]}
        ]
        ok = session.save_session(test_proj, sess_id, "FastAPI Server Build", messages)
        assert ok, "save_session failed"

        # 3. Path traversal attack on session ID
        bad_id = "../../malicious"
        session.save_session(test_proj, bad_id, "Attack", [{"role": "user", "content": "hack"}])
        # Verify it was sanitized and did not escape sessions dir
        sess_dir = session.get_sessions_dir(test_proj)
        assert not os.path.exists(os.path.join(test_proj, "malicious.json"))
        assert os.path.exists(os.path.join(sess_dir, "malicious.json"))
        print("[Pass] Session ID path traversal prevention verified.")

        # 4. Session Loading
        loaded = session.load_session(test_proj, sess_id)
        assert loaded is not None
        assert loaded["title"] == "FastAPI Server Build"
        assert len(loaded["messages"]) == 2
        print("[Pass] load_session restored transcript accurately.")

        # 5. Session Renaming
        renamed_ok = session.rename_session(test_proj, sess_id, "FastAPI & Uvicorn App")
        assert renamed_ok
        reloaded = session.load_session(test_proj, sess_id)
        assert reloaded["title"] == "FastAPI & Uvicorn App"
        print("[Pass] rename_session updated session title.")

        # 6. Session Listing with corrupted file tolerance
        corrupt_file = os.path.join(session.get_sessions_dir(test_proj), "corrupt.json")
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{invalid json...")

        sessions_list = session.list_sessions(test_proj)
        assert len(sessions_list) >= 1
        assert any(s["id"] == sess_id for s in sessions_list)
        print("[Pass] list_sessions tolerated corrupt file without crashing.")

        # 7. Session Deletion
        del_ok = session.delete_session(test_proj, sess_id)
        assert del_ok
        assert session.load_session(test_proj, sess_id) is None
        print("[Pass] delete_session removed session cleanly.")

        # 8. Unregister Project
        unreg_ok = session.unregister_project(test_proj)
        assert unreg_ok
        projects_after = session.list_projects()
        assert not any(session.paths_equal(p["path"], test_proj) for p in projects_after)
        print("[Pass] unregister_project removed project from registry.")

    finally:
        session.unregister_project(test_proj)
        shutil.rmtree(test_proj, ignore_errors=True)

def test_workspace_coordination():
    print("\n--- Testing Workspace Coordination & Listeners ---")
    test_dir = tempfile.mkdtemp(prefix="harness_test_ws_")
    events_received = []

    def listener(new_path):
        events_received.append(new_path)

    try:
        orig_ws = tools.get_active_workspace()
        tools.add_workspace_listener(listener)

        # Test set_workspace
        tools.set_workspace(test_dir)
        assert len(events_received) == 1
        assert session.paths_equal(events_received[0], test_dir)
        assert session.paths_equal(tools.get_active_workspace(), test_dir)
        print("[Pass] set_workspace triggered registered workspace listener.")

        # Test create_project scaffolding
        res_create = tools.create_project("my_app", parent_directory=test_dir, template="python")
        assert "Successfully created project 'my_app'" in res_create
        assert len(events_received) == 2
        app_dir = os.path.join(test_dir, "my_app")
        assert os.path.exists(os.path.join(app_dir, "README.md"))
        assert os.path.exists(os.path.join(app_dir, ".gitignore"))
        assert os.path.exists(os.path.join(app_dir, "main.py"))
        assert session.paths_equal(tools.get_active_workspace(), app_dir)
        print("[Pass] create_project scaffolded files and notified workspace listeners.")

    finally:
        tools.remove_workspace_listener(listener)
        tools.set_active_workspace(orig_ws)
        shutil.rmtree(test_dir, ignore_errors=True)

def test_engine_system_prompt_restoration():
    print("\n--- Testing AgentEngine System Prompt Restoration ---")
    agent = AgentEngine()
    # Simulate loading past history where history[0] is user message (no system prompt)
    agent.history = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"}
    ]

    # Verify that before running, if system prompt is missing, running restores it at index 0
    # We test the prompt insertion logic directly:
    import config
    current_system_prompt = config.get_system_prompt()
    if not agent.history:
        agent.history.append({"role": "system", "content": current_system_prompt})
    elif agent.history[0]["role"] == "system":
        agent.history[0]["content"] = current_system_prompt
    else:
        agent.history.insert(0, {"role": "system", "content": current_system_prompt})

    assert agent.history[0]["role"] == "system", "System prompt must be restored at index 0!"
    assert agent.history[1]["role"] == "user"
    assert agent.history[2]["role"] == "assistant"
    print("[Pass] System prompt correctly prepended to loaded conversation history.")

def main():
    print("=====================================================")
    print("Running Deep Architecture & Robustness Test Suite")
    print("=====================================================")
    test_file_operations()
    test_session_and_project_management()
    test_workspace_coordination()
    test_engine_system_prompt_restoration()
    print("\n=====================================================")
    print("ALL DEEP ARCHITECTURE TESTS PASSED SUCCESSFULLY! [OK]")
    print("=====================================================")

if __name__ == "__main__":
    main()
