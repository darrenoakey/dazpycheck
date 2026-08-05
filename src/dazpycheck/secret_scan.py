from __future__ import annotations

import ast
import os


def check_legacy_secret_access(directory: str) -> tuple[bool, str]:
    """Reject Python runtime paths that can invoke the retired macOS credential stack."""
    errors: list[str] = []
    excluded = {".git", ".venv", "venv", "env", "node_modules", "site-packages", "build", "dist"}
    forbidden_modules = {"keyring", "securitykeyring"}
    process_calls = {"run", "call", "check_call", "check_output", "Popen"}

    for root, dirs, files in os.walk(directory):
        dirs[:] = [name for name in dirs if name not in excluded]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, encoding="utf-8") as source_file:
                    tree = ast.parse(source_file.read(), filename=path)
            except (OSError, SyntaxError, UnicodeError):
                continue
            for node in ast.walk(tree):
                imported: list[str] = []
                if isinstance(node, ast.Import):
                    imported = [alias.name.split(".", 1)[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = [node.module.split(".", 1)[0]]
                for module in imported:
                    if module in forbidden_modules:
                        errors.append(f"{path}:{node.lineno}: retired credential module import: {module}")

                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr not in process_calls or not node.args:
                    continue
                command_literals = {
                    value.value
                    for value in ast.walk(node.args[0])
                    if isinstance(value, ast.Constant) and isinstance(value.value, str)
                }
                if command_literals & {"security", "/usr/bin/security"}:
                    errors.append(f"{path}:{node.lineno}: retired macOS security command invocation")

    if errors:
        return False, "\n".join(errors)
    return True, ""
