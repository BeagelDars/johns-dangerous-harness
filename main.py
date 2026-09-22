"""
Main Interactive CLI for the Agent Harness.
"""
import sys
import os
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness.engine import AgentEngine
from harness.registry import registry
import config

def print_banner(agent: AgentEngine):
    print("=" * 60)
    print("   JOHNS DANGEROUS HARNESS - HYBRID AI AGENT")
    print(f"  Mode:      {agent.active_mode.upper()} {'(Auto-routes Local vs Cloud)' if agent.active_mode == 'auto' else ''}")
    print(f"  Model:     {agent.model}")
    print(f"  Max Steps: {agent.max_steps}")
    print(f"  Tools:     {len(registry.get_schemas())} registered tools")
    print("  Commands:  'exit' to quit | 'clear' to reset | 'tools' to list")
    print("             'model <auto|gemini|local>' | 'steps <n>' to change step limit")
    print("=" * 60)

def display_tools():
    print("\n--- REGISTERED TOOLS ---")
    for s in registry.get_schemas():
        fn = s["function"]
        params = list(fn.get("parameters", {}).get("properties", {}).keys())
        print(f"  * {fn['name']}({', '.join(params)})")
        print(f"    {fn['description']}")
    print("------------------------\n")

def main():
    agent = AgentEngine()
    print_banner(agent)

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("\nShutting down harness. Goodbye!")
                break

            if user_input.lower() == "clear":
                agent.history = []
                print("\n[History reset]")
                continue

            if user_input.lower() == "tools":
                display_tools()
                continue

            if user_input.lower().startswith("steps"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    agent.max_steps = int(parts[1])
                    print(f"\n[Max Steps updated to {agent.max_steps}]")
                else:
                    print(f"\nCurrent Max Steps: {agent.max_steps}")
                    print("Usage: steps <number> (e.g. 'steps 30')")
                continue

            if user_input.lower().startswith("model") or user_input.lower().startswith("switch"):
                parts = user_input.split()
                if len(parts) > 1:
                    target = parts[1].lower()
                    if agent.switch_profile(target):
                        if target == "auto":
                            print("\n[Mode switched to 'AUTO'] -> Dynamically routes between Local (routine) & Gemini (complex).")
                        else:
                            print(f"\n[Switched to '{target}'] -> Model: {agent.model} ({agent.base_url})")
                    else:
                        print(f"\n[Unknown option '{target}']. Available: ['auto', 'gemini', 'local']")
                else:
                    print(f"\nCurrent Mode: {agent.active_mode.upper()} (Model: {agent.model})")
                    print("Available: 'auto', 'gemini', 'local'")
                    print("Usage: model auto | model gemini | model local")
                continue

            print("\n[Agent Thinking...]")
            stream = agent.run(user_input)

            final_text = ""
            for event in stream:
                etype = event.get("type")
                if etype == "routing":
                    print(f"  >> [Auto-Route] -> {event['target'].upper()} ({event['model']})")
                    print(f"     Reason: {event['reason']}")
                elif etype == "model_fallback":
                    print(f"  >> [Model Fallback] -> Switched from {event.get('from')} to {event.get('to')}")
                    print(f"     Reason: {event.get('reason')}")
                elif etype == "step_start":
                    print(f"  -> Step {event['step']}")
                elif etype == "tool_call":
                    print(f"    [TOOL CALL] {event['tool']}({json.dumps(event['args'])})")
                elif etype == "tool_result":
                    out_preview = str(event['output'])
                    if len(out_preview) > 200:
                        out_preview = out_preview[:200] + "... [truncated]"
                    print(f"    [TOOL RESULT] {out_preview}")
                elif etype == "final_answer":
                    final_text = event.get("content", "")
                elif etype == "circuit_breaker":
                    final_text = event.get("content", "")
                elif etype == "error":
                    print(f"    [ERROR] {event['error']}")

            print(f"\nAgent > {final_text}")

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            continue
        except Exception as e:
            print(f"\n[Unexpected Error]: {e}")

if __name__ == "__main__":
    main()
