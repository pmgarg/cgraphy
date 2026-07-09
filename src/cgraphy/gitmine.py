import subprocess
from collections import Counter
from itertools import combinations

MARKER = "__CGRAPHY_COMMIT__"


def commit_blocks(root, max_commits=1000):
    """Yield (sha, [files]) for recent commits, newest first."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--name-only",
             f"--pretty=format:{MARKER}%H%n%s", f"-n{max_commits}"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    for block in out.stdout.split(MARKER):
        lines = block.splitlines()
        if not lines or not lines[0].strip():
            continue
        sha = lines[0].strip()
        subject = lines[1].strip() if len(lines) > 1 else ""
        files = sorted({ln.strip() for ln in lines[2:] if ln.strip()})
        yield sha, subject, files


def mine_cochanges(db, root, max_commits=1000, min_support=3,
                   max_files_per_commit=50, exclude_shas=None):
    pairs = Counter()
    for sha, _subject, files in commit_blocks(root, max_commits) or []:
        if exclude_shas and sha in exclude_shas:
            continue
        if len(files) < 2 or len(files) > max_files_per_commit:
            continue
        for a, b in combinations(files, 2):
            pairs[(a, b)] += 1
    frequent = {p: c for p, c in pairs.items() if c >= min_support}
    if not frequent:
        return
    mx = max(frequent.values())
    file_ids = {r["file_path"]: r["id"] for r in db.file_nodes()}
    for (a, b), count in frequent.items():
        ia, ib = file_ids.get(a), file_ids.get(b)
        if ia and ib:
            db.add_edge(ia, ib, "co_changes", weight=count / mx)
    db.commit()
