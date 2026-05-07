SKILL_NAME = "doc_generator"
SKILL_DESCRIPTION = "Génère automatiquement documentation README, docstrings Python et JSDoc JavaScript"
SKILL_VERSION = "1.0.0"

import ast
from datetime import datetime
from pathlib import Path
import re


try:
    from file_tools import read_file, write_file
except ImportError:
    read_file = None
    write_file = None


def run(action, **kwargs):
    try:
        action_name = str(action or "").strip().lower()

        if action_name == "readme":
            return _readme(
                kwargs.get("project_dir"),
                kwargs.get("project_name"),
                kwargs.get("description"),
                kwargs.get("features"),
                kwargs.get("usage"),
                kwargs.get("output"),
            )

        if action_name == "docstrings":
            return _docstrings(kwargs.get("path"), kwargs.get("apply", False))

        if action_name == "jsdoc":
            return _jsdoc(kwargs.get("path"), kwargs.get("apply", False))

        if action_name == "project":
            return _project(
                kwargs.get("project_dir"),
                kwargs.get("project_name"),
                kwargs.get("project_type"),
            )

        return _error(f"Action inconnue: {action}")
    except Exception as error:
        return _error(str(error))


def _readme(project_dir, project_name, description, features, usage, output):
    if not project_name:
        return _error("project_name est requis")

    output_path = Path(output) if output else Path(project_dir or ".") / "README.md"
    content = _readme_content(project_name, description, features, usage)
    _write_text(output_path, content)

    return {
        "success": True,
        "content": content,
        "file_path": str(output_path),
        "functions_found": [],
        "error": "",
    }


def _docstrings(path, apply):
    file_path = Path(path)

    if not file_path.exists():
        return _error(f"Fichier introuvable: {file_path}")

    source = _read_text(file_path)
    tree = ast.parse(source)
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    missing = [node for node in functions if ast.get_docstring(node) is None]
    function_names = [node.name for node in missing]
    updated = source

    for node in sorted(missing, key=lambda item: item.lineno, reverse=True):
        updated = _insert_python_docstring(updated, node)

    if apply:
        _write_text(file_path, updated)

    return {
        "success": True,
        "content": updated,
        "file_path": str(file_path),
        "functions_found": function_names,
        "error": "",
    }


def _jsdoc(path, apply):
    file_path = Path(path)

    if not file_path.exists():
        return _error(f"Fichier introuvable: {file_path}")

    source = _read_text(file_path)
    matches = list(re.finditer(r"(^|\n)([ \t]*)(function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\(([^)]*)\)\s*=>)", source))
    functions_found = []
    updated = source

    for match in reversed(matches):
        start = match.start(2)
        prefix = source[max(0, start - 8):start]

        if "/**" in prefix:
            continue

        name = match.group(4) or match.group(6)
        params_text = match.group(5) or match.group(7) or ""
        params = [item.strip() for item in params_text.split(",") if item.strip()]
        indent = match.group(2)
        functions_found.append(name)
        doc = _jsdoc_block(name, params, indent)
        updated = updated[:start] + doc + updated[start:]

    functions_found.reverse()

    if apply:
        _write_text(file_path, updated)

    return {
        "success": True,
        "content": updated,
        "file_path": str(file_path),
        "functions_found": functions_found,
        "error": "",
    }


def _project(project_dir, project_name, project_type):
    root = Path(project_dir or ".")
    project_type = str(project_type or "").lower()

    if project_type not in {"python", "node", "html"}:
        return _error(f"project_type non supporte: {project_type}")

    readme_result = _readme(root, project_name or root.name, f"Projet {project_name or root.name}.", [], "", root / "README.md")
    functions_found = []
    summaries = [f"README: {readme_result.get('file_path', '')}"]

    if project_type == "python":
        for file_path in root.glob("*.py"):
            result = _docstrings(file_path, False)
            functions_found.extend(result.get("functions_found", []))
            summaries.append(f"Docstrings proposees: {file_path}")

    if project_type in {"node", "html"}:
        for file_path in list(root.glob("*.js")) + list(root.glob("js/*.js")):
            result = _jsdoc(file_path, False)
            functions_found.extend(result.get("functions_found", []))
            summaries.append(f"JSDoc propose: {file_path}")

    return {
        "success": True,
        "content": "\n".join(summaries),
        "file_path": str(root),
        "functions_found": functions_found,
        "error": "",
    }


def _readme_content(project_name, description, features, usage):
    feature_items = features or []

    if isinstance(feature_items, str):
        feature_items = [item.strip() for item in feature_items.split(",") if item.strip()]

    lines = [
        f"# {project_name}",
        "",
        str(description or "Documentation projet."),
        "",
        "## Fonctionnalites",
        "",
    ]

    if feature_items:
        lines.extend(f"- {item}" for item in feature_items)
    else:
        lines.append("- A completer")

    lines.extend([
        "",
        "## Utilisation",
        "",
        str(usage or "A completer"),
        "",
        "## Generation",
        "",
        f"Document genere le {datetime.utcnow().isoformat()}Z.",
        "",
    ])

    return "\n".join(lines)


def _insert_python_docstring(source, node):
    lines = source.splitlines()
    insert_index = node.lineno
    indent = " " * (node.col_offset + 4)
    params = [arg.arg for arg in node.args.args]
    doc_lines = [
        f'{indent}"""Auto-generated documentation.',
        "",
    ]

    if params:
        doc_lines.append(f"{indent}Args:")
        doc_lines.extend(f"{indent}    {param}: Description." for param in params)
        doc_lines.append("")

    if _has_return(node):
        doc_lines.append(f"{indent}Returns:")
        doc_lines.append(f"{indent}    Description.")
        doc_lines.append("")

    doc_lines.append(f'{indent}"""')
    lines[insert_index:insert_index] = doc_lines
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def _jsdoc_block(name, params, indent):
    lines = [
        f"{indent}/**",
        f"{indent} * {name}.",
    ]
    lines.extend(f"{indent} * @param {{any}} {param}" for param in params)
    lines.append(f"{indent} * @returns {{any}}")
    lines.append(f"{indent} */")
    return "\n".join(lines) + "\n"


def _has_return(node):
    return any(isinstance(item, ast.Return) and item.value is not None for item in ast.walk(node))


def _read_text(path):
    if read_file:
        return read_file(path)

    with Path(path).open("r", encoding="utf-8") as file:
        return file.read()


def _write_text(path, content):
    if write_file:
        write_file(path, content)
        return

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as file:
        file.write(content)


def _error(message):
    return {
        "success": False,
        "content": "",
        "file_path": "",
        "functions_found": [],
        "error": message,
    }
