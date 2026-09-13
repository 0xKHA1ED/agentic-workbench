# AI Workflow v2 Phase 0: Immediate Cleanup & Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute Phase 0 of the AI Workflow v2 architecture proposal: eliminate dead prototype code (`meal`/`allergy` handlers), fix the fragment pending proposal blindness in `tree_server.py`, establish a deterministic repository root resolver, and create the baseline unit test suite.

**Architecture:** Refactor `scripts/project_tree/` and `scripts/tree_server.py` in place with zero breaking changes to the external CLI API. Implement an upward-walking root resolver in `scripts/project_tree/resolver.py`, purge dead prototype operations from `ops.py` and `cli.py`, and link `list_pending_proposals` to the server state. Enforce safety with a comprehensive stdlib `unittest` test suite in `ai-workflow/tests/`.

**Tech Stack:** Python 3.10+, stdlib `unittest`, stdlib `pathlib`, `http.server`, PyYAML 6.0+.

**Spec:** `ai-workflow/meta/docs/ARCHITECTURE-V2-PROPOSAL.md` (Section 11, Phase 0)

## Global Constraints

- Zero third-party dependencies beyond PyYAML (`PyYAML>=6.0`). Use stdlib `unittest` for all tests.
- All existing CLI commands (`show`, `compose`, `list-fragments`, `validate-patterns`, `propose`, `apply`, `reject`) must remain 100% backward-compatible.
- Repository root resolution must never guess relative parent paths; it must search upwards for `.workflow/config.yaml` or `.git`.
- Dead operations (`include-meal`, `exclude-meal`, `add-allergies`) must be deleted from both `ops.py` and `cli.py`.
- `tree_server.py` must report pending proposals for both root `nodes.yaml.proposed` and any fragment `fragments/*.yaml.proposed`.

---

### Task 1: Test Infrastructure & Baseline Suite

**Files:**
- Create: `ai-workflow/tests/__init__.py`
- Create: `ai-workflow/tests/test_model.py`
- Create: `ai-workflow/tests/test_ops.py`

**Interfaces:**
- Consumes: `scripts/project_tree/model.py`, `scripts/project_tree/ops.py`
- Produces: Runnable test suite via `python3 -m unittest discover ai-workflow/tests`

- [ ] **Step 1: Write baseline tests for `model.py`**

Create `ai-workflow/tests/test_model.py` with tests covering:
- `resolve_project_name`: alias resolution (`ai-workflow` -> `meta`).
- `list_projects`: discovers `meta`, examples, and host projects.
- `nodes_path` and `proposed_path`: correct paths for given project names.
- `list_pending_proposals`: returns root and fragment `.proposed` files.
- `load_tree` and `find_node_in_tree`.

- [ ] **Step 2: Write baseline tests for `ops.py`**

Create `ai-workflow/tests/test_ops.py` with tests covering:
- `add_child`: adding children to root and nested groups.
- `set_data`: updating node data dictionary.
- `set_status`: updating status enum (`weak`, `strong`, etc.).
- `reparent`: moving a node from one parent to another.
- `mark_stale`: marking node as stale.
- `apply_batch`: atomic multi-operation application.

- [ ] **Step 3: Run the test suite to verify baseline passes**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-workflow/tests/
git commit -m "test(ai-workflow): add baseline unit test suite for model and ops"
```

---

### Task 2: Purge Dead Prototype Code

**Files:**
- Modify: `ai-workflow/scripts/project_tree/ops.py:148-207,227-254`
- Modify: `ai-workflow/scripts/project_tree/cli.py:453-475`
- Test: `ai-workflow/tests/test_ops.py`

**Interfaces:**
- Consumes: `ops.OP_HANDLERS`, `cli.main`
- Produces: Cleaned operation registry without `include-meal`, `exclude-meal`, `add-allergies`.

- [ ] **Step 1: Add tests verifying dead operations are removed and raise errors**

In `ai-workflow/tests/test_ops.py`, add `test_dead_operations_removed`:
```python
def test_dead_operations_removed(self):
    for op in ["include-meal", "exclude-meal", "add-allergies"]:
        with self.subTest(op=op):
            self.assertNotIn(op, ops.OP_HANDLERS)
            with self.assertRaises(ValueError):
                ops.apply_op({"nodes": []}, op, ["test"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_ops.py -v`
Expected: FAIL (`AssertionError: 'include-meal' unexpectedly found in OP_HANDLERS`).

- [ ] **Step 3: Delete dead code from `ops.py` and `cli.py`**

1. In `ai-workflow/scripts/project_tree/ops.py`:
   - Delete `include_meal` (lines 148–177).
   - Delete `exclude_meal` (lines 180–206).
   - Delete `add_allergies` (lines 227–254).
2. In `ai-workflow/scripts/project_tree/cli.py`:
   - Delete the handlers for `include-meal`, `exclude-meal`, and `add-allergies` in `cmd_propose` (lines 453–458 and 463–474).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/project_tree/ops.py ai-workflow/scripts/project_tree/cli.py ai-workflow/tests/test_ops.py
git commit -m "refactor(ai-workflow): purge meal and allergy prototype residue"
```

---

### Task 3: Fix Pending Proposal Detection in Tree Server

**Files:**
- Modify: `ai-workflow/scripts/tree_server.py:52-67`
- Create: `ai-workflow/tests/test_tree_server.py`

**Interfaces:**
- Consumes: `scripts/project_tree/model.py:list_pending_proposals`
- Produces: `tree_server.TreeHandler._load_tree(name)` with `pending` (boolean) and `pending_targets` (list of strings).

- [ ] **Step 1: Write test for tree_server pending proposal behavior**

Create `ai-workflow/tests/test_tree_server.py` using `unittest.mock` or temp directories:
- Test tree with no proposals: `data["pending"] == False`, `data["pending_targets"] == []`.
- Test tree with fragment proposal (`fragments/sim.yaml.proposed`): `data["pending"] == True`, `"fragments/sim.yaml" in data["pending_targets"]`.
- Test tree with root proposal (`nodes.yaml.proposed`): `data["pending"] == True`, `"nodes.yaml" in data["pending_targets"]`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: FAIL on fragment proposal test (`AssertionError: False is not true`).

- [ ] **Step 3: Update `tree_server.py` to use `list_pending_proposals`**

In `ai-workflow/scripts/tree_server.py`, modify `_load_tree(self, name: str) -> dict`:
```python
    def _load_tree(self, name: str) -> dict:
        from project_tree.model import nodes_path, resolve_project_name, list_pending_proposals

        name = resolve_project_name(name)
        path = nodes_path(name)
        if not path.exists():
            raise FileNotFoundError(name)
        with path.open() as f:
            data = yaml.safe_load(f)
        pending_list = list_pending_proposals(name)
        data["pending"] = len(pending_list) > 0
        data["pending_targets"] = [p[0] or "nodes.yaml" for p in pending_list]
        try:
            data = fragments.compose_tree(data, name)
        except (FileNotFoundError, ValueError) as exc:
            data["compose_error"] = str(exc)
        return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/tree_server.py ai-workflow/tests/test_tree_server.py
git commit -m "fix(ai-workflow): detect fragment pending proposals in tree server"
```

---

### Task 4: Deterministic Host Repository Root Resolver

**Files:**
- Create: `ai-workflow/scripts/project_tree/resolver.py`
- Modify: `ai-workflow/scripts/project_tree/model.py:16-26`
- Create: `ai-workflow/tests/test_resolver.py`

**Interfaces:**
- Consumes: Filesystem path traversal
- Produces: `find_repository_root(start_path: Path | None = None) -> Path`

- [ ] **Step 1: Write tests for `find_repository_root`**

Create `ai-workflow/tests/test_resolver.py`:
- Test root detection with `.workflow/config.yaml` present in an ancestor directory.
- Test root detection with `.git` directory present in an ancestor directory.
- Test fallback to start path / cwd when neither is found.
- Test that it does not guess parent directories arbitrarily.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_resolver.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'project_tree.resolver'`).

- [ ] **Step 3: Implement `find_repository_root` in `resolver.py` and integrate with `model.py`**

1. Create `ai-workflow/scripts/project_tree/resolver.py`:
```python
from __future__ import annotations
from pathlib import Path

def find_repository_root(start_path: Path | None = None) -> Path:
    """
    Deterministically find the true host repository root.
    Walks up from start_path looking for:
      1. .workflow/config.yaml (v2 project marker)
      2. .git directory
    Never guesses parent directories.
    """
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr, *curr.parents]:
        if (parent / ".workflow" / "config.yaml").exists():
            return parent
        if (parent / ".git").exists():
            return parent
    return curr
```
2. Update `ai-workflow/scripts/project_tree/model.py`:
Replace `host_root()` with:
```python
from project_tree.resolver import find_repository_root

def host_root() -> Path:
    """Repository that hosts the package."""
    return find_repository_root(PACKAGE_ROOT)

REPO_ROOT = host_root()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/project_tree/resolver.py ai-workflow/scripts/project_tree/model.py ai-workflow/tests/test_resolver.py
git commit -m "feat(ai-workflow): add deterministic repository root resolver"
```

---

### Task 5: End-to-End Verification & CLI Sanity Pass

**Files:**
- Create: `ai-workflow/tests/test_cli_e2e.py`

**Interfaces:**
- Consumes: `ai-workflow/scripts/project_tree.py` CLI
- Produces: Automated E2E verification of CLI execution on `meta` and `tik`.

- [ ] **Step 1: Write E2E CLI test script**

Create `ai-workflow/tests/test_cli_e2e.py` testing subprocess runs:
- `project_tree.py show meta` (exits 0, outputs `AI Workflow`).
- `project_tree.py compose meta` (exits 0, outputs valid YAML).
- `project_tree.py list-fragments meta` (exits 0, outputs fragment paths).
- `project_tree.py validate-patterns meta --recursive` (exits 0).
- `project_tree.py show tik` (exits 0, outputs `WHICH ONE WINS`).

- [ ] **Step 2: Run E2E tests**

Run: `python3 -m unittest ai-workflow/tests/test_cli_e2e.py -v`
Expected: PASS across all commands.

- [ ] **Step 3: Run the full test suite**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: 100% PASS with 0 failures.

- [ ] **Step 4: Commit**

```bash
git add ai-workflow/tests/test_cli_e2e.py
git commit -m "test(ai-workflow): add e2e CLI sanity tests for meta and tik"
```
