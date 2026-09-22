import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from harness.engine import AgentEngine

def test_live():
    print("Connecting harness to Qwen 2.5 7B...")
    agent = AgentEngine()
    query = "What is 157 * 392? Use your calculate tool to find the exact answer."
    print(f"User Query: {query}")

    for event in agent.run(query):
        etype = event.get("type")
        if etype == "step_start":
            print(f"➜ Step {event['step']}")
        elif etype == "tool_call":
            print(f"  [Tool Call]: {event['tool']} with {event['args']}")
        elif etype == "tool_result":
            print(f"  [Tool Result]: {event['output']}")
        elif etype == "final_answer":
            print(f"Agent Final Answer: {event['content']}")
        elif etype == "error":
            print(f"Error: {event['error']}")

if __name__ == "__main__":
    test_live()
