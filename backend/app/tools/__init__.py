from .read_file import ReadFileTool
from .run_python import RunPythonTool
from .run_shell import RunShellTool
from .registry import register_tool

# Registrar ferramentas
register_tool(ReadFileTool())
register_tool(RunPythonTool())
register_tool(RunShellTool())