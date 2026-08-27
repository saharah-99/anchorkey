# anchorkey: research/educational reference implementation for a technical paper series.
# Provided as-is under Apache-2.0 (no warranty); a personal learning project, not a commercial product.
"""
test_public_api.py — pin the published surface of the package.

WHY THIS FILE EXISTS

Three places describe the API and they drifted apart: `entity_resolution/__init__`
exported `describe`, the staged v0.2.0 quickstart imported it from the top-level
package, and the top-level package did not export it. Nothing caught that, because
every individual file was internally consistent and the test suite never imported the
quickstart. The failure only appeared when the quickstart was actually run.

These tests make the surface itself the thing under test, so a re-export removed in one
place fails here rather than in a user's terminal.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import anchorkey

_ROOT = Path(__file__).resolve().parents[1]

# The published surface. Adding to this is a deliberate act; it should require editing
# this list, which is the point.
EXPECTED_API = {"normalize", "natural_key", "same_entity", "needs_review", "describe"}


def test_top_level_all_is_exactly_the_published_surface():
    assert set(anchorkey.__all__) == EXPECTED_API


def test_everything_in_all_is_actually_importable():
    """__all__ can list a name the module never binds; that fails only at `from x import *`."""
    for name in anchorkey.__all__:
        assert hasattr(anchorkey, name), f"__all__ advertises {name!r} but the module has no such attribute"
        assert callable(getattr(anchorkey, name)), f"{name!r} is exported but not callable"


def test_docstring_documents_every_exported_name():
    """The 'Public API:' block is what a reader trusts; keep it honest."""
    doc = anchorkey.__doc__ or ""
    for name in EXPECTED_API:
        assert re.search(rf"^\s*{re.escape(name)}\(", doc, re.M), (
            f"{name!r} is exported but absent from the Public API block of the package docstring"
        )


def test_subpackage_reexports_are_a_subset_of_the_top_level():
    """Anything entity_resolution publishes should be reachable from the top level.

    This is the exact drift that broke the staged quickstart: the subpackage exported
    `describe` and the top level did not.
    """
    from anchorkey import entity_resolution

    missing = set(entity_resolution.__all__) - EXPECTED_API
    assert not missing, (
        f"entity_resolution exports {sorted(missing)} which the top-level package does not "
        "re-export; either promote them or drop them from the subpackage __all__"
    )


@pytest.mark.parametrize("script", ["examples/quickstart.py", "release-v2/quickstart.py"])
def test_quickstart_only_imports_names_the_package_exports(script: str):
    """Parses the import statement rather than executing, so a held script is still checked.

    `release-v2/quickstart.py` is the staged v0.2.0 onboarding path. It is not on the
    normal import path and no other test touches it, which is why its ImportError went
    unnoticed until someone ran it by hand.
    """
    path = _ROOT / script
    if not path.exists():
        pytest.skip(f"{script} not present")

    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "anchorkey":
            imported.update(alias.name for alias in node.names)

    unknown = imported - EXPECTED_API
    assert not unknown, f"{script} imports {sorted(unknown)} from anchorkey, which does not export them"


def _git(*args: str) -> str | None:
    """Run a git command in the repo, or return None if git/repo is unavailable."""
    if shutil.which("git") is None or not (_ROOT / ".git").exists():
        return None
    try:
        out = subprocess.run(["git", "-C", str(_ROOT), *args],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def test_every_submodule_the_package_imports_is_tracked_by_git():
    """`import anchorkey` must not depend on a module that git will not ship.

    THIS IS THE MOST IMPORTANT TEST IN THE REPO, and it guards a failure that no other
    check can see. The layered-release pattern holds a subpackage out of the public tree
    via .gitignore while it stays on disk for local development. Everything passes
    locally, because the working tree HAS the held files. `git status` shows only a small
    edit to __init__.py and looks perfectly safe to commit. What actually ships is a
    package whose __init__ imports a subpackage that is not in the repository, so
    `import anchorkey` raises ModuleNotFoundError for every user, including existing ones
    who upgrade.

    That is exactly the state this repo was in throughout v0.2.0 preparation: __init__.py
    imported `.entity_resolution`, which had zero files tracked in HEAD.

    Keeping this as a test rather than a release checklist is deliberate. The v0.2.0
    checklist lived in release-v2/RESTORE.md, which is itself gitignored and is deleted
    once the release is done, so the safeguard would have vanished at the moment it first
    proved useful. The same hold pattern is planned for Paper 3, so the risk recurs. This
    file is committed and survives.
    """
    tracked = _git("ls-files")
    if tracked is None:
        pytest.skip("git or .git not available; cannot check what would ship")

    tracked_paths = set(tracked.split())
    init = _ROOT / "src" / "anchorkey" / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"))

    # Relative imports in __init__.py: `from .entity_resolution import ...` -> entity_resolution
    submodules = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level and node.module
    }

    untracked = []
    for sub in sorted(submodules):
        pkg = f"src/anchorkey/{sub}"
        if not any(p == f"{pkg}.py" or p.startswith(f"{pkg}/") for p in tracked_paths):
            untracked.append(sub)

    assert not untracked, (
        "src/anchorkey/__init__.py imports " + ", ".join(repr(u) for u in untracked) +
        ", which git does not track. Committing as-is ships a package where "
        "`import anchorkey` raises ModuleNotFoundError for every user.\n"
        "Fix: un-ignore src/anchorkey/<name>/ and commit it in the SAME commit as "
        "__init__.py, or drop the import until that layer ships."
    )


def test_version_is_consistent_across_packaging_metadata():
    """__init__, pyproject and CITATION.cff must agree.

    They are currently allowed to disagree only while the v0.2.0 release is unfinished;
    see release-v2/RESTORE.md step 4. This test is what stops a half-finished bump from
    shipping silently.
    """
    init_v = anchorkey.__version__
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    citation = (_ROOT / "CITATION.cff").read_text(encoding="utf-8")

    py_v = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M).group(1)
    cff_v = re.search(r'^version:\s*"([^"]+)"', citation, re.M).group(1)

    assert init_v == py_v == cff_v, (
        f"version drift: __init__={init_v}, pyproject={py_v}, CITATION.cff={cff_v}. "
        "Bump all three in the same commit (RESTORE.md step 4)."
    )
