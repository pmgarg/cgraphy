import json

from cgraphy.init_cmd import init_project


def test_init_creates_mcp_json_and_steering_files(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    pass\n")
    out = init_project(tmp_path)
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert mcp["mcpServers"]["cgraphy"]["command"] == "uvx"
    assert "cgraphy" in (tmp_path / "CLAUDE.md").read_text()
    assert "cgraphy_search" in (tmp_path / "AGENTS.md").read_text()
    assert "Codex" in out  # printed guidance mentions other surfaces


def test_init_appends_without_duplicating(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# My project\n\nExisting notes.\n")
    init_project(tmp_path)
    init_project(tmp_path)  # second run must not duplicate
    text = (tmp_path / "CLAUDE.md").read_text()
    assert text.count("cgraphy_search") == 1
    assert text.startswith("# My project")


def test_init_merges_existing_mcp_json(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers": {"other": {"command": "x", "args": []}}}')
    init_project(tmp_path)
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert set(mcp["mcpServers"]) == {"other", "cgraphy"}
