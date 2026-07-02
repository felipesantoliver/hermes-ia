from typing import Dict, List, Type
from .base import Tool

_tool_registry: Dict[str, Tool] = {}

def register_tool(tool: Tool):
    _tool_registry[tool.name] = tool

def get_tool(name: str) -> Tool:
    return _tool_registry.get(name)

def list_tools() -> List[Tool]:
    return list(_tool_registry.values())

def to_llm_schema(tools: List[Tool]) -> List[Dict]:
    """Converte lista de tools para formato function calling do OpenAI."""
    schema = []
    for tool in tools:
        schema.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        })
    return schema