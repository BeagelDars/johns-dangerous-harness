"""
Tool Registry: Inspects Python functions and generates standard tool schemas.
"""
import inspect
from typing import Callable, Any, Dict, List, get_type_hints

TYPE_MAPPING = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, func: Callable) -> Callable:
        """Decorator to register a Python function as an agent tool."""
        name = func.__name__
        doc = inspect.getdoc(func) or "No description provided."
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = type_hints.get(param_name, str)
            json_type = TYPE_MAPPING.get(param_type, "string")

            properties[param_name] = {
                "type": json_type,
                "description": f"Parameter: {param_name}"
            }

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": doc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

        self._tools[name] = func
        self._schemas.append(schema)
        return func

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns all tool schemas for model payload."""
        return self._schemas

    def execute(self, name: str, kwargs: Dict[str, Any]) -> str:
        """Executes a registered tool by name with arguments."""
        if name not in self._tools:
            return f"Error: Tool '{name}' is not registered."
        try:
            result = self._tools[name](**kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing '{name}': {type(e).__name__}: {e}"

# Global registry instance
registry = ToolRegistry()
tool = registry.register
