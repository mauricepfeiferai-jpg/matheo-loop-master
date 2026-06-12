"""Project Scanner — Python-Port von Understand-Anything Agent #1.
Scannt ein Projekt-Verzeichnis und produziert JSON-Inventory:
  files[], languages[], frameworks[], importMap, complexity"""

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

# Erweiterung → Sprache (canonical)
EXT_LANG = {
    ".py": "python", ".pyx": "python", ".pyi": "python",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".md": "markdown", ".mdx": "markdown", ".rst": "markdown",
    ".txt": "text", ".text": "text",
    ".json": "json", ".jsonc": "json", ".toml": "toml",
    ".yaml": "yaml", ".yml": "yaml",
    ".sql": "sql", ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf", ".prisma": "prisma",
    ".html": "html", ".htm": "html", ".css": "css",
    ".scss": "scss", ".sass": "scss", ".less": "less",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".rb": "ruby", ".php": "php",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    ".cs": "csharp", ".swift": "swift",
    ".tf": "terraform", ".tfvars": "terraform",
    ".dockerfile": "dockerfile", ".env": "env",
    ".cfg": "config", ".ini": "config", ".conf": "config",
    ".xml": "xml", ".xsl": "xml", ".xsd": "xml",
    ".csv": "csv", ".tsv": "tsv",
    ".ps1": "powershell", ".psm1": "powershell", ".psd1": "powershell",
    ".bat": "batch", ".cmd": "batch",
    ".gradle": "gradle", ".mod": "go", ".sum": "go",
    ".gradle.kts": "gradle",
}

FILENAME_LANG = {
    "dockerfile": "dockerfile", "dockerfile.": "dockerfile",
    "makefile": "makefile", "jenkinsfile": "jenkinsfile",
    "procfile": "procfile", "vagrantfile": "vagrantfile",
    "gemfile": "ruby", "rakefile": "ruby",
}

# Kategorie nach Pfad/Extension
CATEGORY_RULES = [
    # Filename-exakte Matches (höchste Priorität)
    (lambda p: p.name.lower() == "license", "code"),
    (lambda p: p.name.lower().startswith("dockerfile"), "infra"),
    (lambda p: p.name.lower().startswith("docker-compose") or p.name.lower().startswith("compose."), "infra"),
    (lambda p: p.name.lower() == "makefile", "infra"),
    (lambda p: p.name.lower() == "jenkinsfile", "infra"),
    (lambda p: p.name.lower() == "procfile", "infra"),
    (lambda p: p.name.lower() == "vagrantfile", "infra"),
    (lambda p: ".github/workflows/" in str(p).lower(), "infra"),
    (lambda p: ".circleci/" in str(p).lower(), "infra"),
    (lambda p: ".gitlab-ci.yml" in str(p).lower(), "infra"),
    (lambda p: "k8s/" in str(p).lower() or "kubernetes/" in str(p).lower(), "infra"),
    (lambda p: p.suffix.lower() in (".k8s.yml", ".k8s.yaml"), "infra"),
    # Extension-based
    (lambda p: p.suffix.lower() in (".md", ".mdx", ".rst", ".txt", ".text"), "docs"),
    (lambda p: p.suffix.lower() in (".yaml", ".yml", ".json", ".jsonc", ".toml", ".xml", ".xsl", ".xsd", ".plist", ".cfg", ".ini", ".env", ".properties", ".csproj", ".sln", ".mod", ".sum", ".gradle", ".gradle.kts"), "config"),
    (lambda p: p.suffix.lower() in (".tf", ".tfvars"), "infra"),
    (lambda p: p.suffix.lower() in (".sql", ".graphql", ".gql", ".proto", ".prisma", ".csv", ".tsv"), "data"),
    (lambda p: p.suffix.lower() in (".sh", ".bash", ".zsh", ".ps1", ".psm1", ".psd1", ".bat", ".cmd"), "script"),
    (lambda p: p.suffix.lower() in (".html", ".htm", ".css", ".scss", ".sass", ".less"), "markup"),
]


def _detect_language(path: Path) -> str:
    name_lower = path.name.lower()
    if name_lower in FILENAME_LANG:
        return FILENAME_LANG[name_lower]
    if name_lower.startswith("dockerfile."):
        return "dockerfile"
    if path.suffix.lower() in EXT_LANG:
        return EXT_LANG[path.suffix.lower()]
    # Spezialfälle ohne Extension
    if name_lower in ("dockerfile", "makefile", "jenkinsfile"):
        return name_lower
    return "unknown"


def _detect_category(path: Path) -> str:
    for rule, cat in CATEGORY_RULES:
        try:
            if rule(path):
                return cat
        except Exception:
            continue
    return "code"


def _count_lines(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# Python-Import-Extraktion via AST
def _extract_python_imports(path: Path, project_root: Path) -> list[str]:
    import ast
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except Exception:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
            elif node.level and node.level > 0:
                # relative import
                imports.append(f".{node.level}")
    return imports


def _resolve_python_imports(imports: list[str], source_path: Path, project_root: Path, file_map: dict[str, Path]) -> list[str]:
    """Versucht Python-Imports zu Dateipfaden aufzulösen (projekt-intern)."""
    resolved: list[str] = []
    source_dir = source_path.parent
    for imp in imports:
        if imp.startswith("."):
            # Relative: versuche __init__.py oder Modul im selben/übergeordneten Verzeichnis
            level = len(imp) - len(imp.lstrip("."))
            rel = source_dir
            for _ in range(level - 1):
                rel = rel.parent
            # Versuche verschiedene Kandidaten
            candidates = [
                rel / "__init__.py",
                rel / f"{imp.lstrip('.')}.py",
            ]
        else:
            # Absolute: Suche im Projekt-Root
            candidates = [
                project_root / f"{imp.replace('.', '/')}.py",
                project_root / imp / "__init__.py",
                project_root / f"{imp.replace('.', '/')}" / "__init__.py",
            ]
        for cand in candidates:
            try:
                rel = cand.relative_to(project_root)
                rel_str = str(rel)
                if rel_str in file_map:
                    resolved.append(rel_str)
                    break
            except ValueError:
                continue
    return resolved


# Bash-Import-Heuristik (source, . , executable-Aufrufe)
_BASH_IMPORT_RE = re.compile(r'(?:^|\s)(?:source|\.)\s+["\']?([^"\'\s;]+)')
_BASH_SHEBANG_RE = re.compile(r'^#!.*\b(bash|sh|zsh|python3?|node|perl|ruby)')


def _extract_shell_imports(path: Path, project_root: Path, file_map: dict[str, Path]) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return []

    imports: list[str] = []
    for m in _BASH_IMPORT_RE.finditer(text):
        raw = m.group(1)
        # Versuche aufzulösen
        cand = path.parent / raw
        if not cand.exists():
            cand = project_root / raw
        if cand.exists():
            try:
                rel = cand.relative_to(project_root)
                if str(rel) in file_map:
                    imports.append(str(rel))
            except ValueError:
                pass
    return imports


def _get_frameworks(project_root: Path) -> list[str]:
    """Erkennt Frameworks aus Manifest-Dateien."""
    frameworks: set[str] = set()
    files = {p.name.lower(): p for p in project_root.iterdir() if p.is_file()}

    # Python
    if "requirements.txt" in files:
        try:
            with open(files["requirements.txt"], "r", encoding="utf-8", errors="replace") as f:
                content = f.read().lower()
                fw_map = {
                    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
                    "sqlalchemy": "SQLAlchemy", "alembic": "Alembic",
                    "celery": "Celery", "pydantic": "Pydantic",
                    "pytest": "pytest", "uvicorn": "Uvicorn",
                    "aiohttp": "aiohttp", "tornado": "Tornado",
                    "starlette": "Starlette", "channels": "Django Channels",
                }
                for key, name in fw_map.items():
                    if key in content:
                        frameworks.add(name)
        except Exception:
            pass

    if "pyproject.toml" in files:
        try:
            with open(files["pyproject.toml"], "r", encoding="utf-8", errors="replace") as f:
                content = f.read().lower()
                for key, name in {
                    "poetry": "Poetry", "hatch": "Hatch", "pdm": "PDM",
                    "setuptools": "setuptools", "flit": "Flit",
                }.items():
                    if key in content:
                        frameworks.add(name)
        except Exception:
            pass

    # Node
    if "package.json" in files:
        try:
            with open(files["package.json"], "r", encoding="utf-8", errors="replace") as f:
                pkg = json.load(f)
            deps = {k.lower(): v for k, v in {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {})
            }.items()}
            fw_map = {
                "react": "React", "vue": "Vue", "svelte": "Svelte",
                "@angular/core": "Angular", "express": "Express",
                "fastify": "Fastify", "next": "Next.js", "nuxt": "Nuxt",
                "vite": "Vite", "vitest": "Vitest", "jest": "Jest",
                "tailwindcss": "TailwindCSS", "prisma": "Prisma",
                "redux": "Redux", "zustand": "Zustand",
            }
            for key, name in fw_map.items():
                if key in deps:
                    frameworks.add(name)
        except Exception:
            pass

    # Infra-Tools
    infra = {
        "dockerfile": "Docker",
        "docker-compose.yml": "Docker Compose",
        "docker-compose.yaml": "Docker Compose",
        "compose.yml": "Docker Compose",
        "compose.yaml": "Docker Compose",
    }
    for fname, fw in infra.items():
        if fname in files or (project_root / fname).exists():
            frameworks.add(fw)

    if any((project_root / ".github" / "workflows").glob("*.yml") if (project_root / ".github" / "workflows").exists() else []):
        frameworks.add("GitHub Actions")

    if any(project_root.glob("*.tf")):
        frameworks.add("Terraform")

    return sorted(frameworks)


def _get_readme_description(project_root: Path) -> tuple[str, str]:
    """Liest README/package.json für Name + Beschreibung."""
    name = project_root.name
    description = ""

    readme_candidates = ["README.md", "README.rst", "README.txt", "README"]
    for cand in readme_candidates:
        p = project_root / cand
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    lines = [f.readline().strip() for _ in range(15)]
                # Erste nicht-leere Zeile nach dem Titel
                desc_lines = [l for l in lines if l and not l.startswith("#") and len(l) > 20]
                if desc_lines:
                    description = desc_lines[0][:200]
                break
            except Exception:
                pass

    pkg = project_root / "package.json"
    if pkg.exists():
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", name)
            description = data.get("description", description) or description
        except Exception:
            pass

    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, "r", encoding="utf-8") as f:
                content = f.read()
            m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.M)
            if m:
                name = m.group(1)
            m = re.search(r'^\s*description\s*=\s*["\']([^"\']+)["\']', content, re.M)
            if m:
                description = m.group(1)
        except Exception:
            pass

    return name, description


def _default_understandignore() -> list[str]:
    return [
        ".git", ".gitignore", ".github", ".gitlab-ci.yml",
        ".vscode", ".idea", "__pycache__", "*.pyc", "*.pyo",
        ".pytest_cache", ".mypy_cache", "*.egg-info",
        "node_modules", ".npm", ".pnpm", ".yarn",
        "venv", ".venv", "env", ".env", "virtualenv",
        "dist", "build", "*.egg", "*.whl",
        ".understand-anything", ".claude", ".cursor", ".copilot",
        "*.min.js", "*.min.css", "*.map",
        "coverage", ".coverage", "htmlcov",
        "*.lock", "*.log", "*.tmp", "*.temp",
        ".DS_Store", "Thumbs.db",
        "*.class", "*.jar", "target/",
        "*.o", "*.obj", "*.so", "*.dll", "*.dylib",
        "*.wasm", "*.bin",
        "*.mp4", "*.mp3", "*.wav", "*.avi", "*.mov",
        "*.jpg", "*.jpeg", "*.png", "*.gif", "*.svg", "*.ico",
        "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx",
        "*.zip", "*.tar", "*.gz", "*.bz2", "*.rar", "*.7z",
    ]


def _should_ignore(path: Path, patterns: list[str]) -> bool:
    """Prüft ob ein Pfad gegen .understandignore Patterns matched."""
    spath = str(path)
    parts = path.parts

    for pat in patterns:
        pat = pat.strip()
        if not pat or pat.startswith("#"):
            continue
        neg = pat.startswith("!")
        if neg:
            pat = pat[1:]

        # Directory-Match
        if pat.endswith("/"):
            dir_pat = pat.rstrip("/")
            if any(part == dir_pat or part.endswith("/" + dir_pat) for part in parts):
                return not neg
            continue

        # Wildcard-Match
        if "*" in pat:
            # simple glob check
            import fnmatch
            if fnmatch.fnmatch(path.name, pat):
                return not neg
            if any(fnmatch.fnmatch(part, pat) for part in parts):
                return not neg
            continue

        # Exact-Match oder Subpath
        if pat in parts:
            return not neg
        if path.name == pat or spath.endswith("/" + pat):
            return not neg

    return False


def scan_project(project_root: Path, custom_ignore: list[str] | None = None) -> dict:
    """Haupteinstieg: Scant ein Projekt und gibt Inventory-Dict zurück."""
    root = project_root.resolve()

    # Ignore-Patterns sammeln
    ignore_patterns = _default_understandignore()
    custom_file = root / ".understandignore"
    if custom_file.exists():
        try:
            with open(custom_file, "r", encoding="utf-8") as f:
                ignore_patterns.extend(line.strip() for line in f if line.strip() and not line.strip().startswith("#"))
        except Exception:
            pass
    if custom_ignore:
        ignore_patterns.extend(custom_ignore)

    # Dateien auflisten (git ls-files bevorzugt)
    files: list[Path] = []
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(root), capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            for raw in result.stdout.split("\x00"):
                if raw:
                    p = root / raw
                    if p.exists() and not _should_ignore(p, ignore_patterns):
                        files.append(p)
    except Exception:
        pass

    # Fallback: rekursiver Walk
    if not files:
        for p in root.rglob("*"):
            if p.is_file() and not _should_ignore(p.relative_to(root), ignore_patterns):
                files.append(p)

    # Dateien sortieren und verarbeiten
    files.sort(key=lambda p: str(p.relative_to(root)))

    file_entries: list[dict] = []
    file_map: dict[str, Path] = {}  # rel-path → abs-path
    for p in files:
        rel = str(p.relative_to(root))
        file_map[rel] = p
        lang = _detect_language(p)
        cat = _detect_category(p)
        lines = _count_lines(p)
        file_entries.append({
            "path": rel,
            "language": lang,
            "sizeLines": lines,
            "fileCategory": cat,
        })

    # Statistiken
    by_category = Counter(e["fileCategory"] for e in file_entries)
    by_language = Counter(e["language"] for e in file_entries if e["language"] != "unknown")
    total = len(file_entries)
    filtered = 0  # Wir tracken das nicht exakt, da git ls-files schon filtert

    # Komplexität
    if total < 20:
        complexity = "minimal"
    elif total < 100:
        complexity = "moderate"
    elif total < 500:
        complexity = "complex"
    else:
        complexity = "very complex"

    # Import-Map bauen
    import_map: dict[str, list[str]] = {}
    for e in file_entries:
        rel = e["path"]
        abs_p = file_map[rel]
        lang = e["language"]

        if lang == "python":
            raw = _extract_python_imports(abs_p, root)
            resolved = _resolve_python_imports(raw, abs_p, root, file_map)
            import_map[rel] = resolved
        elif lang in ("shell", "bash", "zsh"):
            import_map[rel] = _extract_shell_imports(abs_p, root, file_map)
        else:
            import_map[rel] = []

    # Name + Beschreibung
    name, description = _get_readme_description(root)
    frameworks = _get_frameworks(root)
    languages = sorted(set(e["language"] for e in file_entries if e["language"] != "unknown"))

    return {
        "name": name,
        "description": description or "No description available",
        "languages": languages,
        "frameworks": frameworks,
        "files": file_entries,
        "totalFiles": total,
        "filteredByIgnore": filtered,
        "estimatedComplexity": complexity,
        "importMap": import_map,
    }


def scan_and_write(project_root: Path, out_path: Path | None = None) -> dict:
    """Scannt und schreibt JSON."""
    result = scan_project(project_root)
    if out_path is None:
        out_path = project_root / ".understand-anything" / "intermediate" / "scan-result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result
