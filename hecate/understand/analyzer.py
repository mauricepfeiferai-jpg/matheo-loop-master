"""File Analyzer — Python-Port von Understand-Anything Agent #2.
Extrahiert aus Source-Files:
  functions, classes, exports, callGraph, metrics
Nutzt Python ast (kein tree-sitter nötig)."""

import ast
import json
from pathlib import Path


def extract_structure(path: Path) -> dict:
    """Liest eine Datei und extrahiert strukturelle Daten via AST."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as e:
        return {"error": str(e), "functions": [], "classes": [], "exports": [], "callGraph": [], "metrics": {}}

    total_lines = source.count("\n") + 1
    non_empty = sum(1 for l in source.splitlines() if l.strip())

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "error": f"SyntaxError: {e}",
            "totalLines": total_lines,
            "nonEmptyLines": non_empty,
            "functions": [], "classes": [], "exports": [], "callGraph": [], "metrics": {}
        }

    functions: list[dict] = []
    classes: list[dict] = []
    exports: list[dict] = []
    call_graph: list[dict] = []

    # Visitor für Funktionen, Klassen, Calls
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            functions.append({
                "name": node.name,
                "startLine": node.lineno,
                "endLine": getattr(node, "end_lineno", node.lineno),
                "params": params,
            })
        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node
            ]
            props = [
                t.targets[0].id
                for n in ast.walk(node)
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                for t in [n]
            ]
            classes.append({
                "name": node.name,
                "startLine": node.lineno,
                "endLine": getattr(node, "end_lineno", node.lineno),
                "methods": methods,
                "properties": list(dict.fromkeys(props)),  # dedup
            })

    # Exports: Top-Level Funktionen/Klassen + __all__
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            exports.append({"name": node.name, "line": node.lineno, "isDefault": False})
        elif isinstance(node, ast.ClassDef):
            exports.append({"name": node.name, "line": node.lineno, "isDefault": False})

    # Call-Graph: einfache Heuristik
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Finde den umschließenden Funktions-Namen
            caller = None
            for parent in ast.walk(tree):
                # Das ist nicht trivial mit ast.walk — wir machen es pragmatisch:
                # Wir nutzen die Zeilennummer
                pass
            # Vereinfacht: Wir matchen Calls anhand von Namen
            if isinstance(node.func, ast.Name):
                callee = node.func.id
                # Wir können den Caller nicht einfach ermitteln ohne Parent-Traversal
                # Stattdessen: speichern wir nur den Callee-Namen
                call_graph.append({"callee": callee, "lineNumber": node.lineno})

    metrics = {
        "importCount": len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]),
        "exportCount": len(exports),
        "functionCount": len(functions),
        "classCount": len(classes),
    }

    return {
        "totalLines": total_lines,
        "nonEmptyLines": non_empty,
        "functions": functions,
        "classes": classes,
        "exports": exports,
        "callGraph": call_graph,
        "metrics": metrics,
    }


def analyze_batch(files: list[dict], import_map: dict[str, list[str]]) -> dict:
    """Analysiert einen Batch von Dateien und baut Knowledge-Graph Fragment.
    files: Liste von dicts mit path, language, sizeLines, fileCategory
    import_map: projekt-interne Imports
    """
    nodes: list[dict] = []
    edges: list[dict] = []

    for fmeta in files:
        path = fmeta["path"]
        lang = fmeta["language"]
        cat = fmeta["fileCategory"]
        abs_path = Path(path) if path.startswith("/") else Path("/") / path

        # File-Node
        node_type = _file_node_type(cat, abs_path)
        summary = _summarize_file(cat, abs_path.name, lang)
        tags = _tags_for(cat, abs_path.name, lang)
        complexity = _complexity_for(fmeta.get("sizeLines", 0))

        nodes.append({
            "id": f"file:{path}",
            "type": node_type,
            "name": abs_path.name,
            "filePath": path,
            "summary": summary,
            "tags": tags,
            "complexity": complexity,
        })

        # Für Code-Dateien: Funktionen + Klassen extrahieren
        if cat == "code" and lang == "python" and abs_path.exists():
            struct = extract_structure(abs_path)
            for fn in struct.get("functions", []):
                if _is_significant(fn, struct.get("exports", [])):
                    nodes.append({
                        "id": f"function:{path}:{fn['name']}",
                        "type": "function",
                        "name": fn["name"],
                        "filePath": path,
                        "lineRange": [fn["startLine"], fn["endLine"]],
                        "summary": _summarize_function(fn),
                        "tags": ["function", lang],
                        "complexity": _complexity_for(fn["endLine"] - fn["startLine"] + 1),
                    })
                    edges.append({
                        "source": f"file:{path}",
                        "target": f"function:{path}:{fn['name']}",
                        "type": "contains",
                        "direction": "forward",
                        "weight": 1.0,
                    })

            for cls in struct.get("classes", []):
                if _is_significant_class(cls):
                    nodes.append({
                        "id": f"class:{path}:{cls['name']}",
                        "type": "class",
                        "name": cls["name"],
                        "filePath": path,
                        "lineRange": [cls["startLine"], cls["endLine"]],
                        "summary": _summarize_class(cls),
                        "tags": ["class", lang],
                        "complexity": _complexity_for(cls["endLine"] - cls["startLine"] + 1),
                    })
                    edges.append({
                        "source": f"file:{path}",
                        "target": f"class:{path}:{cls['name']}",
                        "type": "contains",
                        "direction": "forward",
                        "weight": 1.0,
                    })

        # Import-Edges
        for imp in import_map.get(path, []):
            edges.append({
                "source": f"file:{path}",
                "target": f"file:{imp}",
                "type": "imports",
                "direction": "forward",
                "weight": 0.7,
            })

    return {"nodes": nodes, "edges": edges}


def _file_node_type(cat: str, path: Path) -> str:
    if cat == "code":
        return "file"
    if cat == "config":
        return "config"
    if cat == "docs":
        return "document"
    if cat == "infra":
        if "docker" in path.name.lower():
            return "service"
        if ".github" in str(path).lower():
            return "pipeline"
        if path.suffix in (".tf", ".tfvars"):
            return "resource"
        return "service"
    if cat == "data":
        if path.suffix == ".sql":
            return "table"
        if path.suffix in (".graphql", ".proto", ".prisma"):
            return "schema"
        return "schema"
    if cat == "script":
        return "file"
    if cat == "markup":
        return "file"
    return "file"


def _summarize_file(cat: str, name: str, lang: str) -> str:
    if cat == "code":
        return f"{lang.title()}-Quelldatei {name}."
    if cat == "config":
        return f"Konfigurationsdatei {name}."
    if cat == "docs":
        return f"Dokumentation {name}."
    if cat == "infra":
        return f"Infrastruktur-Definition {name}."
    if cat == "data":
        return f"Daten/Schema-Definition {name}."
    if cat == "script":
        return f"Shell-Skript {name}."
    return f"Datei {name}."


def _tags_for(cat: str, name: str, lang: str) -> list[str]:
    tags = [cat]
    if "test" in name.lower() or "spec" in name.lower():
        tags.append("test")
    if name.lower() in ("main.py", "app.py", "index.py", "__init__.py"):
        tags.append("entry-point")
    if name.lower() == "readme.md":
        tags.append("documentation")
    tags.append(lang)
    return tags[:5]


def _complexity_for(lines: int) -> str:
    if lines < 50:
        return "simple"
    if lines < 200:
        return "moderate"
    return "complex"


def _is_significant(fn: dict, exports: list[dict]) -> bool:
    if fn["endLine"] - fn["startLine"] + 1 >= 10:
        return True
    if any(e["name"] == fn["name"] for e in exports):
        return True
    return False


def _is_significant_class(cls: dict) -> bool:
    if len(cls.get("methods", [])) >= 2:
        return True
    if cls["endLine"] - cls["startLine"] + 1 >= 20:
        return True
    return False


def _summarize_function(fn: dict) -> str:
    params = ", ".join(fn.get("params", [])) or "keine"
    return f"Funktion {fn['name']}({params})."


def _summarize_class(cls: dict) -> str:
    methods = ", ".join(cls.get("methods", [])[:3]) or "keine"
    return f"Klasse {cls['name']} mit Methoden: {methods}."
