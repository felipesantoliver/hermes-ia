import pytest
from app.tools import ReadFileTool, RunPythonTool, RunShellTool

def test_read_file_not_found():
    tool = ReadFileTool()
    result = tool.run(project_id="fake", file_path="nonexistent.txt")
    assert not result.success
    assert "não encontrado" in result.error

def test_run_python_success():
    tool = RunPythonTool()
    result = tool.run(code="print('hello')")
    assert result.success
    assert result.data.strip() == "hello"

def test_run_python_error():
    tool = RunPythonTool()
    result = tool.run(code="raise ValueError('teste')")
    assert not result.success
    assert "teste" in result.error

def test_run_shell_allowed():
    tool = RunShellTool()
    result = tool.run(command="echo 'ok'")
    assert result.success
    assert "ok" in result.data

def test_run_shell_disallowed():
    tool = RunShellTool()
    result = tool.run(command="rm -rf /")
    assert not result.success
    assert "não permitido" in result.error