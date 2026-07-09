import subprocess

from cgraphy.db import GraphDB
from cgraphy.gitmine import mine_cochanges


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo)})


def make_git_repo(tmp_path):
    git(tmp_path, "init", "-q")
    for i in range(3):
        (tmp_path / "a.py").write_text(f"# v{i}\n")
        (tmp_path / "b.py").write_text(f"# v{i}\n")
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "-q", "-m", f"c{i}")
    (tmp_path / "c.py").write_text("# once\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "c3")
    return tmp_path


def test_cochange_edges_for_frequent_pairs(tmp_path):
    repo = make_git_repo(tmp_path)
    db = GraphDB(tmp_path / "g.db")
    fa = db.add_node("file", "a.py", "a.py", file_path="a.py")
    fb = db.add_node("file", "b.py", "b.py", file_path="b.py")
    fc = db.add_node("file", "c.py", "c.py", file_path="c.py")
    mine_cochanges(db, repo)
    edges = {(e["source_id"], e["target_id"], e["kind"]) for e in db.all_edges()}
    assert (fa, fb, "co_changes") in edges or (fb, fa, "co_changes") in edges
    assert not any(fc in (s, t) for s, t, k in edges if k == "co_changes")


def test_no_git_repo_is_silent(tmp_path):
    db = GraphDB(tmp_path / "g.db")
    mine_cochanges(db, tmp_path)  # must not raise
    assert db.all_edges() == []
