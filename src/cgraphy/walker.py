import os
from pathlib import Path

import pathspec

MAX_FILE_BYTES = 1_000_000

LANGUAGE_BY_EXT = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".rs": "rust",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".kt": "kotlin",
    ".swift": "swift", ".scala": "scala", ".lua": "lua", ".sh": "bash",
    ".bash": "bash", ".zsh": "bash", ".pl": "perl", ".r": "r", ".jl": "julia",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang", ".hs": "haskell",
    ".ml": "ocaml", ".dart": "dart", ".zig": "zig", ".sql": "sql",
}

TEXT_EXTS = {".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini",
             ".cfg", ".csv", ".env.example", ".xml", ".html", ".css", ".proto",
             ".graphql", ".tf", ".dockerfile", ".gitignore", ".cgraphyignore"}

SKIP_DIRS = {".git", ".hg", ".svn", ".cgraphy", "node_modules", ".venv", "venv",
             "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build",
             ".idea", ".vscode", ".tox", "target", ".next", ".cache"}


def relpath(root, path) -> str:
    return Path(path).relative_to(root).as_posix()


def _load_ignores(root: Path):
    lines = []
    for name in (".gitignore", ".cgraphyignore"):
        f = root / name
        if f.is_file():
            lines += f.read_text(errors="replace").splitlines()
    if not lines:
        return None
    try:
        return pathspec.GitIgnoreSpec.from_lines(lines)
    except AttributeError:  # pathspec < 0.10
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def iter_files(root):
    root = Path(root)
    spec = _load_ignores(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
            and not (spec and spec.match_file(relpath(root, Path(dirpath) / d) + "/")))
        for fn in sorted(filenames):
            if fn.endswith((".min.js", ".min.css", ".lock")):
                continue
            p = Path(dirpath) / fn
            rel = relpath(root, p)
            if spec and spec.match_file(rel):
                continue
            ext = p.suffix.lower() if p.suffix else p.name.lower()
            lang = LANGUAGE_BY_EXT.get(ext)
            if lang is None and ext not in TEXT_EXTS:
                continue
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield p, lang
