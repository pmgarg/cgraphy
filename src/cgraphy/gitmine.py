import subprocess
from collections import Counter
from itertools import combinations

MARKER = "__CGRAPHY_COMMIT__"


def mine_cochanges(db, root, max_commits=1000, min_support=3,
                   max_files_per_commit=50):
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--name-only",
             f"--pretty=format:{MARKER}", f"-n{max_commits}"],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    pairs = Counter()
    for block in out.stdout.split(MARKER):
        files = sorted({ln.strip() for ln in block.splitlines() if ln.strip()})
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
