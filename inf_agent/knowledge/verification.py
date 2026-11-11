"""Optional source diagnostics, without execution approval or knowledge claims."""

import ast
from pathlib import Path


def inspect_source(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return {"success": False, "errors": [str(error)], "warnings": []}
    warnings = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and node.attr in {"use_auto_smooth", "auto_smooth_angle"}
        ):
            warnings.append(
                {
                    "line": node.lineno,
                    "message": "Blender 4 removed mesh.use_auto_smooth/auto_smooth_angle; use sharp edges or face smoothing",
                }
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "new_node"
            and any(
                isinstance(arg, ast.Attribute)
                and arg.attr == "Bump"
                or isinstance(arg, ast.Constant)
                and arg.value == "ShaderNodeBump"
                for arg in node.args
            )
        ):
            warnings.append(
                {
                    "line": node.lineno,
                    "message": "Infinigen's default material path rejects Bump nodes; use supported displacement or roughness variation",
                }
            )
    return {"success": True, "errors": [], "warnings": warnings}
