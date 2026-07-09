from pathlib import Path

from cgraphy.walker import iter_files, relpath


def make(root: Path, rel: str, text: str = "x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_yields_language_for_known_extensions(tmp_path):
    make(tmp_path, "a.py"); make(tmp_path, "b.rs"); make(tmp_path, "c.yaml")
    got = {relpath(tmp_path, p): lang for p, lang in iter_files(tmp_path)}
    assert got == {"a.py": "python", "b.rs": "rust", "c.yaml": None}


def test_respects_gitignore_and_cgraphyignore(tmp_path):
    make(tmp_path, ".gitignore", "build/\n")
    make(tmp_path, ".cgraphyignore", "vendor/\n")
    make(tmp_path, "build/x.py"); make(tmp_path, "vendor/y.py"); make(tmp_path, "ok.py")
    got = {relpath(tmp_path, p) for p, _ in iter_files(tmp_path)}
    assert "ok.py" in got and "build/x.py" not in got and "vendor/y.py" not in got


def test_skips_minified_and_lock_files(tmp_path):
    make(tmp_path, "vendor.min.js"); make(tmp_path, "styles.min.css")
    make(tmp_path, "uv.lock"); make(tmp_path, "ok.js")
    got = {relpath(tmp_path, p) for p, _ in iter_files(tmp_path)}
    assert got == {"ok.js"}


def test_skips_dot_dirs_binaries_and_big_files(tmp_path):
    make(tmp_path, ".git/config"); make(tmp_path, ".cgraphy/graph.db")
    (tmp_path / "img.png").write_bytes(b"\x89PNG")
    make(tmp_path, "big.py", "x" * 1_100_000)
    make(tmp_path, "ok.py")
    got = {relpath(tmp_path, p) for p, _ in iter_files(tmp_path)}
    assert got == {"ok.py"}
