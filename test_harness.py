"""
Quick self-test for tool schemas and execution.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness.registry import registry
from harness import tools

def run_tests():
    schemas = registry.get_schemas()
    print(f"Total tools registered: {len(schemas)}")
    for s in schemas:
        fn = s["function"]
        print(f"  * {fn['name']}: {fn['description']}")

    # Test calculate
    c_res = registry.execute("calculate", {"expression": "25 * 4 + math.sqrt(144)"})
    print(f"\n[Test calculate]: {c_res} (Expected: 112.0)")
    assert float(c_res) == 112.0

    # Test run_python_code
    py_res = registry.execute("run_python_code", {"code": "x = [i**2 for i in range(5)]; print(x)"})
    print(f"[Test run_python_code]: {py_res}")
    assert "[0, 1, 4, 9, 16]" in py_res

    # Test run_powershell
    ps_res = registry.execute("run_powershell", {"command": "Write-Output 'Harness PowerShell Working'"})
    print(f"[Test run_powershell]: {ps_res}")
    assert "Harness PowerShell Working" in ps_res

    # Test web_search
    ws_res = registry.execute("web_search", {"query": "python official website", "max_results": 2})
    print(f"[Test web_search]: Returned {len(ws_res)} chars")
    assert "python" in ws_res.lower()

    # Test fetch_webpage
    fetch_res = registry.execute("fetch_webpage", {"url": "https://httpbin.org/html", "max_chars": 200})
    print(f"[Test fetch_webpage]: {fetch_res[:60]}...")
    assert len(fetch_res) > 20

    # Test read_file_range
    range_res = registry.execute("read_file_range", {"filepath": "config.py", "start_line": 1, "end_line": 5})
    print(f"[Test read_file_range]:\n{range_res}")
    assert "1:" in range_res

    # Test find_files
    find_res = registry.execute("find_files", {"name_pattern": "*.py", "search_dir": "."})
    print(f"[Test find_files]:\n{find_res[:100]}...")
    assert "config.py" in find_res

    # Test search_file_contents
    grep_res = registry.execute("search_file_contents", {"query": "DEFAULT_PROFILE", "search_dir": "."})
    print(f"[Test search_file_contents]:\n{grep_res[:100]}...")
    assert "config.py" in grep_res

    # Test read_document with created docx
    import docx, os
    d = docx.Document()
    d.add_paragraph("Testing python-docx harness integration.")
    d.save("temp_test_doc.docx")
    try:
        doc_res = registry.execute("read_document", {"filepath": "temp_test_doc.docx"})
        print(f"[Test read_document (docx)]: {doc_res}")
        assert "python-docx harness integration" in doc_res
    finally:
        if os.path.exists("temp_test_doc.docx"):
            os.remove("temp_test_doc.docx")

    # Test memory tools
    mem_save = registry.execute("save_memory", {"key": "test_pref", "note_or_rule": "Always concise"})
    print(f"[Test save_memory]: {mem_save}")
    assert "Successfully saved" in mem_save

    mem_recall = registry.execute("recall_memory", {"key": "test_pref"})
    print(f"[Test recall_memory]: {mem_recall}")
    assert "Always concise" in mem_recall

    mem_del = registry.execute("delete_memory", {"key": "test_pref"})
    print(f"[Test delete_memory]: {mem_del}")
    assert "Successfully deleted" in mem_del

    # Test inspect_image on user file if present
    img_path = r"C:\Users\User\OneDrive\ольга русский 10 класс\ДВОЙНЫЕ СОЮЗЫ 10.png"
    if os.path.exists(img_path):
        img_res = registry.execute("inspect_image", {"filepath": img_path, "question": "What is this image about?"})
        print(f"[Test inspect_image]: {img_res[:80]}...")
    # Test download_file
    dl_target = "temp_downloaded.txt"
    try:
        dl_res = registry.execute("download_file", {"url": "https://httpbin.org/robots.txt", "destination_path": dl_target})
        print(f"[Test download_file]: {dl_res}")
        assert os.path.exists(dl_target)
    finally:
        if os.path.exists(dl_target):
            os.remove(dl_target)

    # Test copy_file, move_file, and delete_file
    test_src = "temp_test_copy_src.txt"
    test_dst = "temp_test_copy_dst.txt"
    test_mv = "temp_test_moved.txt"
    try:
        with open(test_src, "w", encoding="utf-8") as f:
            f.write("Harness file tool test content.")

        cp_res = registry.execute("copy_file", {"source": test_src, "destination": test_dst})
        print(f"[Test copy_file]: {cp_res}")
        assert os.path.exists(test_dst)
        with open(test_dst, "r", encoding="utf-8") as f:
            assert f.read() == "Harness file tool test content."

        mv_res = registry.execute("move_file", {"source": test_dst, "destination": test_mv})
        print(f"[Test move_file]: {mv_res}")
        assert not os.path.exists(test_dst)
        assert os.path.exists(test_mv)

        # Safe delete (trash)
        del_safe_res = registry.execute("delete_file", {"filepath": test_mv, "permanent": False})
        print(f"[Test delete_file (safe)]: {del_safe_res}")
        assert not os.path.exists(test_mv)
        assert "trash" in del_safe_res.lower()

        # Permanent delete
        del_perm_res = registry.execute("delete_file", {"filepath": test_src, "permanent": True})
        print(f"[Test delete_file (permanent)]: {del_perm_res}")
        assert not os.path.exists(test_src)

        # Safety guard test: deleting active workspace or drive root must be refused
        guard_res = registry.execute("delete_file", {"filepath": "C:\\"})
        print(f"[Test delete_file safety guard]: {guard_res}")
        assert "CRITICAL SAFETY ERROR" in guard_res
    finally:
        for p in (test_src, test_dst, test_mv):
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

    # Test Git tools
    git_stat = registry.execute("git_status", {"repo_dir": "."})
    print(f"[Test git_status]:\n{git_stat[:150]}...")
    assert "Git Status" in git_stat or "not a git repository" in git_stat

    git_df = registry.execute("git_diff", {"repo_dir": "."})
    print(f"[Test git_diff]: {git_df[:100]}...")
    assert "changes" in git_df.lower() or "diff" in git_df.lower() or len(git_df) > 0

    print("\nALL TOOL UNIT TESTS PASSED! [OK]")

if __name__ == "__main__":
    run_tests()
