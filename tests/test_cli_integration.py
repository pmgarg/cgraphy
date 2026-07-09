import subprocess
import sys


def test_cli_index_end_to_end(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    pass\n")
    r = subprocess.run([sys.executable, "-m", "cgraphy.cli", "index", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "files" in r.stdout and (tmp_path / ".cgraphy" / "graph.db").exists()
