from .read_file import ReadFileTool
from .run_python import RunPythonTool
from .run_shell import RunShellTool
from .web_search import WebSearchTool
from .codebase_index import CodebaseIndexTool
from .firmware import FirmwareTool
from .security_static import BanditTool, ShellCheckTool
from .ble_config import BLEConfigTool
from .gradle_build import GradleBuildTool
from .layout_validator import LayoutValidatorTool
from .registry import register_tool

# Registrar ferramentas
register_tool(ReadFileTool())
register_tool(RunPythonTool())
register_tool(RunShellTool())
register_tool(WebSearchTool())
register_tool(CodebaseIndexTool())
register_tool(FirmwareTool())
register_tool(BanditTool())
register_tool(ShellCheckTool())
register_tool(BLEConfigTool())
register_tool(GradleBuildTool())
register_tool(LayoutValidatorTool())