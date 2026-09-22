"""
Unit and Integration Tests for Background Tasks, Process Streaming, and Loop Circuit Breaker.
"""
import os
import sys
import time
import json
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness.registry import registry
from harness import tools
from harness.engine import AgentEngine
import config

def test_run_background_process_message_and_output():
    print("\n--- Test 1: run_background_process return message & output capture ---")
    # Start a background script that outputs lines over a few seconds
    code = (
        "import time, sys\n"
        "for i in range(3):\n"
        "    print(f'Line {i+1} from background', flush=True)\n"
        "    time.sleep(0.4)\n"
        "time.sleep(10)\n"
    )
    cmd = f'python -c "{code}"'
    res = registry.execute("run_background_process", {"command": cmd})
    print(f"run_background_process response:\n{res}")

    # Verify return message guidance
    assert "Process is running in background. Do NOT loop or test repeatedly; complete your response now." in res
    assert "Background process started successfully" in res
    assert "[PID: " in res

    # Extract PID
    import re
    m = re.search(r'\[PID:\s*(\d+)\]', res)
    assert m is not None, "PID not found in output"
    pid = int(m.group(1))

    # Check tasks list helper
    tasks = tools.get_background_tasks()
    matching = [t for t in tasks if t["pid"] == pid]
    assert len(matching) == 1, f"Task with PID {pid} not found in active tasks: {tasks}"
    task = matching[0]
    assert task["status"] == "running"
    assert "uptime" in task
    print(f"[Pass] Task found in get_background_tasks(): uptime={task['uptime']}, command={task['command']}")

    # Wait a bit for output lines to arrive
    time.sleep(1.2)
    output = tools.get_background_task_output(pid)
    print(f"Captured output:\n{output}")
    assert "Line 1 from background" in output
    assert "Line 2 from background" in output
    print("[Pass] Output captured asynchronously in streaming buffer.")

    # Test stop_background_process
    stop_res = registry.execute("stop_background_process", {"pid": pid})
    print(f"stop_background_process response: {stop_res}")
    assert "Successfully stopped" in stop_res or "Terminated process" in stop_res

    time.sleep(0.5)
    tasks_after = tools.get_background_tasks()
    assert not any(t["pid"] == pid for t in tasks_after), "Process should no longer be active"
    print("[Pass] stop_background_process terminated the task cleanly.")

def test_background_listener_notifications():
    print("\n--- Test 2: Background task listeners ---")
    notifications = []
    def on_change():
        notifications.append(time.time())

    tools.add_background_listener(on_change)
    try:
        cmd = 'python -c "import time; time.sleep(5)"'
        res = tools.run_background_process(cmd)
        import re
        m = re.search(r'\[PID:\s*(\d+)\]', res)
        pid = int(m.group(1))
        assert len(notifications) >= 1, "Listener should be called on process start"
        prev_count = len(notifications)

        tools.stop_background_process(pid)
        assert len(notifications) > prev_count, "Listener should be called on process stop"
        print(f"[Pass] Background listeners notified: {len(notifications)} times.")
    finally:
        tools.remove_background_listener(on_change)

def test_engine_steering_and_loop_breaker():
    print("\n--- Test 3: Engine process steering & loop circuit breaker ---")
    agent = AgentEngine()
    agent.max_steps = 10

    # We mock _call_api to simulate an LLM that attempts to enter a process verification spiral
    # Turn 1: LLM calls run_background_process
    # Turn 2: LLM calls list_background_processes
    # Turn 3: LLM calls stop_background_process
    step_counter = {"val": 0}

    # Start a dummy script
    dummy_cmd = 'python -c "import time; time.sleep(5)"'

    def mock_call_api(history):
        step_counter["val"] += 1
        st = step_counter["val"]
        if st == 1:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc_1",
                            "function": {
                                "name": "run_background_process",
                                "arguments": json.dumps({"command": dummy_cmd})
                            }
                        }]
                    }
                }]
            }
        elif st == 2:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc_2",
                            "function": {
                                "name": "list_background_processes",
                                "arguments": "{}"
                            }
                        }]
                    }
                }]
            }
        elif st == 3:
            # Stubbornly try to stop process
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc_3",
                            "function": {
                                "name": "stop_background_process",
                                "arguments": json.dumps({"pid": 999999})
                            }
                        }]
                    }
                }]
            }
        else:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Server is running in the background."
                    }
                }]
            }

    agent._call_api = mock_call_api

    events = []
    stream = agent.run("Start the development server")
    for ev in stream:
        events.append(ev)

    # Clean up any background processes started
    tools.terminate_all_processes()

    # Verify steering notice in tool result of turn 2
    tool_results = [e for e in events if e.get("type") == "tool_result"]
    assert len(tool_results) >= 2
    tr2 = tool_results[1]
    assert "[STEERING NOTICE]" in tr2["output"]
    assert "The background process is already running" in tr2["output"]
    print("[Pass] Steering notice successfully injected into list_background_processes tool output.")

    # Verify that circuit breaker tripped on turn 3 instead of running 10 steps
    final_answer = [e for e in events if e.get("type") == "final_answer"]
    assert len(final_answer) == 1
    assert step_counter["val"] <= 4, f"Circuit breaker should stop spiral early, took {step_counter['val']} steps"
    print(f"[Pass] Circuit breaker halted obsessive spiral at step {step_counter['val']}.")

def test_system_prompt_rules():
    print("\n--- Test 4: System prompt operational rules ---")
    prompt = config.get_system_prompt()
    assert "CRITICAL COMPLETION RULE: Once `run_background_process` succeeds" in prompt
    assert "NEVER enter an obsessive verification loop" in prompt
    print("[Pass] System prompt contains strict background completion rules.")

def test_terminated_process_output_retention():
    print("\n--- Test 5: Terminated process output retention ---")
    code = (
        "import time, sys\n"
        "print('Logging startup banner...', flush=True)\n"
        "print('Server bound to port 8080', flush=True)\n"
        "time.sleep(5)\n"
    )
    cmd = f'python -c "{code}"'
    res = registry.execute("run_background_process", {"command": cmd})
    import re
    m = re.search(r'\[PID:\s*(\d+)\]', res)
    assert m is not None
    pid = int(m.group(1))

    time.sleep(1.0)
    # Stop process
    stop_res = registry.execute("stop_background_process", {"pid": pid})
    assert "Successfully stopped" in stop_res or "Terminated process" in stop_res

    # Query output after termination
    out_after = tools.get_background_task_output(pid)
    print(f"Output after termination:\n{out_after}")
    assert "Logging startup banner" in out_after
    assert "Server bound to port 8080" in out_after
    assert "[Process terminated]" in out_after
    print("[Pass] Output for terminated process retained and marked [Process terminated].")

def test_verification_spiral_and_history_integrity():
    print("\n--- Test 6: Socket/urllib spiral breaker & history protocol integrity ---")
    agent = AgentEngine()
    agent.max_steps = 10

    # Step 1: Model calls run_background_process AND an extra tool call tc_extra in the SAME turn
    # Step 2: Model attempts to run urllib socket check in run_python_code
    # Step 3: Model attempts to run netstat in run_powershell -> circuit breaker trips!
    step_counter = {"val": 0}

    def mock_call_api(history):
        step_counter["val"] += 1
        st = step_counter["val"]
        if st == 1:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "tc_bg",
                                "function": {
                                    "name": "run_background_process",
                                    "arguments": json.dumps({"command": 'python -c "import time; time.sleep(5)"'})
                                }
                            },
                            {
                                "id": "tc_pending",
                                "function": {
                                    "name": "calculate",
                                    "arguments": json.dumps({"expression": "1 + 1"})
                                }
                            }
                        ]
                    }
                }]
            }
        elif st == 2:
            # Agent tries urllib inspection
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc_urllib",
                            "function": {
                                "name": "run_python_code",
                                "arguments": json.dumps({"code": "import urllib.request; urllib.request.urlopen('http://localhost:8000')"})
                            }
                        }]
                    }
                }]
            }
        elif st == 3:
            # Agent tries netstat check
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "tc_netstat",
                            "function": {
                                "name": "run_powershell",
                                "arguments": json.dumps({"command": "netstat -ano | findstr 8000"})
                            }
                        }]
                    }
                }]
            }
        else:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "The background process is running."
                    }
                }]
            }

    agent._call_api = mock_call_api

    events = []
    stream = agent.run("Start dev server and test it")
    for ev in stream:
        events.append(ev)

    tools.terminate_all_processes()

    # Verify steering notice in tool result of turn 2
    tool_results = [e for e in events if e.get("type") == "tool_result"]
    urllib_tr = [tr for tr in tool_results if tr.get("tool") == "run_python_code"]
    assert len(urllib_tr) == 1
    assert "[STEERING NOTICE]" in urllib_tr[0]["output"]
    print("[Pass] Steering notice injected into urllib verification tool output.")

    # Verify circuit breaker stopped spiral
    assert step_counter["val"] <= 4, f"Circuit breaker should halt spiral early, took {step_counter['val']} steps"
    print(f"[Pass] Verification spiral halted cleanly at step {step_counter['val']}.")

    # Verify message history integrity for OpenAI API compliance:
    # 1. Every tool_call has a matching tool response
    # 2. History ends with an assistant message
    for i, msg in enumerate(agent.history):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            expected_ids = [tc["id"] for tc in msg["tool_calls"]]
            # Followed by tool responses
            actual_ids = []
            j = i + 1
            while j < len(agent.history) and agent.history[j].get("role") == "tool":
                actual_ids.append(agent.history[j].get("tool_call_id"))
                j += 1
            assert set(expected_ids).issubset(set(actual_ids)), f"Missing tool responses! Expected {expected_ids}, got {actual_ids}"

    assert agent.history[-1].get("role") == "assistant", f"History must end with assistant role, got {agent.history[-1].get('role')}"
    print("[Pass] Message history strictly adheres to OpenAI/Gemini API tool call protocol.")

def main():
    print("=====================================================")
    print("Running Background Tasks & Circuit Breaker Test Suite")
    print("=====================================================")
    test_system_prompt_rules()
    test_run_background_process_message_and_output()
    test_background_listener_notifications()
    test_engine_steering_and_loop_breaker()
    test_terminated_process_output_retention()
    test_verification_spiral_and_history_integrity()
    print("\n=====================================================")
    print("ALL BACKGROUND TASKS & CIRCUIT BREAKER TESTS PASSED! [OK]")
    print("=====================================================")

if __name__ == "__main__":
    main()
