"""Tests for orchestrator/context_loader.py"""

import os
from pathlib import Path
from orchestrator.context_loader import build_file_tree, load_readme, build_context_summary


def test_build_file_tree_basic(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "README.md").write_text("# Hello")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "utils.py").write_text("")

    tree = build_file_tree(str(tmp_path))

    assert "main.py" in tree
    assert "README.md" in tree
    assert "src" in tree
    assert "utils.py" in tree


def test_build_file_tree_skips_hidden_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    (tmp_path / "main.py").write_text("")

    tree = build_file_tree(str(tmp_path))

    assert ".git" not in tree
    assert "main.py" in tree


def test_build_file_tree_skips_pycache(tmp_path):
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-311.pyc").write_bytes(b"")
    (tmp_path / "main.py").write_text("")

    tree = build_file_tree(str(tmp_path))

    assert "__pycache__" not in tree


def test_load_readme_found(tmp_path):
    (tmp_path / "README.md").write_text("# My Project\nHello world")
    readme = load_readme(str(tmp_path))
    assert "My Project" in readme


def test_load_readme_not_found(tmp_path):
    readme = load_readme(str(tmp_path))
    assert readme == ""


def test_load_readme_truncated(tmp_path):
    (tmp_path / "README.md").write_text("x" * 5000)
    readme = load_readme(str(tmp_path))
    assert len(readme) <= 4000


def test_build_context_summary_includes_tree_and_readme(tmp_path):
    (tmp_path / "main.py").write_text("")
    (tmp_path / "README.md").write_text("# Project")

    summary = build_context_summary(str(tmp_path))

    assert "Project File Tree" in summary
    assert "main.py" in summary
    assert "README" in summary
    assert "Project" in summary


def test_build_context_summary_no_readme(tmp_path):
    (tmp_path / "app.py").write_text("")

    summary = build_context_summary(str(tmp_path))

    assert "Project File Tree" in summary
    assert "app.py" in summary
    assert "README" not in summary
