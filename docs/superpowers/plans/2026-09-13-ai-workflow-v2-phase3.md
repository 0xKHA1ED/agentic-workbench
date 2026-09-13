# AI Workflow v2 Phase 3: Executable VERIFY Engine & Auto-Decay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 3 quality system: executable VERIFY assertions in claims/contracts, a shared `verify_runner.py` harness, SHA-256 pattern fingerprinting with auto-decay of `verified_strong` nodes, and Git post-commit + Cockpit on-demand decay scanning.

**Architecture:** Extend `spec_discovery` to validate and emit `execution` blocks on VERIFY claims. Centralize all verification execution in `scripts/project_tree/verify_runner.py` (supporting `command`, `pytest`, `ast_symbol` check types from the v2 schema). Add pattern fingerprint computation to `patterns.py` and a decay scanner that demotes nodes when fingerprints drift without passing re-verification. Wire scanning into `project_tree` CLI, `workflow_mcp`, `tree_server` REST, a lightweight post-commit hook installer, and a Cockpit scan trigger.

**Tech Stack:** Python 3.10+ stdlib (`subprocess`, `hashlib`, `ast`, `pathlib`, `unittest`), PyYAML, Vanilla JS for Cockpit button. Zero new third-party packages.

**Spec:** Section 7 (Quality System), Section 11 (Phase 3), and Appendix A (`verification` / `execution` schema) of `ai-workflow/meta/docs/ARCHITECTURE-V2-PROPOSAL.md`.

## Global Constraints

- Zero third-party dependencies beyond PyYAML (`PyYAML>=6.0`). Standard library only.
- Existing CLI commands (`show`, `compose`, `list-fragments`, `validate-patterns`, `propose`, `apply`, `reject`) and MCP tools must remain 100% backward-compatible.
- `workflow_execute_verification` and `POST /api/verify` must keep their current response shape (`status`, `exit_code`, `stdout`, `stderr`, `duration_seconds`, `command`).
- Decay demotion target status is `decayed_unverified` (not `weak`) when a `verified_strong` node's pattern fingerprint changes and re-verification fails or is absent.
- All existing 181 tests must continue to pass with 0 regressions.
- Hook installer must be opt-in (`project_tree install-decay-hook`); never auto-modify git config without explicit CLI invocation.

---

### Task 1: Executable Claims Schema in `spec_discovery`

**Files:**
- Modify: `ai-workflow/scripts/spec_discovery/model.py`
- Modify: `ai-workflow/scripts/spec_discovery/assemble.py`
- Modify: `ai-workflow/.cursor/skills/scope-contract/SKILL.md`
- Create: `ai-workflow/tests/test_spec_discovery_execution.py`

**Interfaces:**
- Consumes: Claims JSON with optional `execution` object on each claim
- Produces: `normalize_document` validates `execution` when present; `build_markdown` emits executable VERIFY lines

**Execution schema** (on `verify` claims only, optional but validated when present):
```json
{
  "type": "command | pytest | ast_symbol",
  "command": "shell command (required for command/pytest)",
  "target": "pytest node id (pytest only)",
  "symbols": ["SymbolA"] ,
  "file": "path/to/module.py (ast_symbol only)",
  "expected_exit_code": 0,
  "timeout_seconds": 30,
  "stdout_contains": "optional substring"
}
```

- [ ] **Step 1: Write failing tests for execution validation and assembly**

In `ai-workflow/tests/test_spec_discovery_execution.py`:
- Valid claim with `execution.type: command` passes `normalize_document`.
- Invalid execution (missing `command` for type `command`, bad `type` enum) raises `ValueError`.
- `execution` on non-`verify` claim raises `ValueError`.
- `build_markdown` includes executable syntax in VERIFY section when execution present (e.g. `check_type: command | \`echo ok\``).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_spec_discovery_execution.py -v`
Expected: FAIL (validation not implemented).

- [ ] **Step 3: Implement execution validation and assembly output**

In `model.py`: add `VALID_EXECUTION_TYPES`, `validate_execution(claim)`, call from `normalize_document`.
In `assemble.py`: format VERIFY bullets with executable assertion syntax when `execution` present.
In `scope-contract/SKILL.md`: document optional `execution` block in claims JSON (brief, under VERIFY rules).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_spec_discovery_execution.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/spec_discovery/model.py ai-workflow/scripts/spec_discovery/assemble.py ai-workflow/.cursor/skills/scope-contract/SKILL.md ai-workflow/tests/test_spec_discovery_execution.py
git commit -m "feat(spec): add executable execution schema validation for VERIFY claims"
```

---

### Task 2: Shared Verification Runner (`verify_runner.py`)

**Files:**
- Create: `ai-workflow/scripts/project_tree/verify_runner.py`
- Modify: `ai-workflow/scripts/workflow_mcp.py`
- Modify: `ai-workflow/scripts/tree_server.py`
- Create: `ai-workflow/tests/test_verify_runner.py`

**Interfaces:**
- Consumes: Verification spec dict (`check_type`, `command`, `target`, `file`, `symbols`, `expected_exit_code`, `timeout_seconds`, `stdout_contains`) and `cwd: Path`
- Produces: `run_verification(spec, cwd, timeout=30.0) -> dict` with keys: `status`, `command`, `exit_code`, `stdout`, `stderr`, `duration_seconds`

**Check types:**
- `command`: run `spec["command"]` via `subprocess` shell=True
- `pytest`: run `python3 -m pytest <target>` (target required)
- `ast_symbol`: parse `spec["file"]` with `ast`, verify all `symbols` are defined (functions/classes) — no subprocess

Legacy compatibility: if spec is a bare string or dict with only `command`/`cmd` key (no `check_type`), treat as `command`.

- [ ] **Step 1: Write failing tests for verify_runner**

In `ai-workflow/tests/test_verify_runner.py`:
- `command` type: `echo hello` exits 0, stdout captured.
- `command` type: failing command returns `status: failed`.
- `pytest` type: runs a real trivial test file in temp dir.
- `ast_symbol` type: detects exported symbol; fails when symbol missing.
- Legacy string command dict still works.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_verify_runner.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement verify_runner and refactor callers**

Create `verify_runner.py` with `normalize_verification_spec(data) -> dict` and `run_verification(spec, cwd, timeout)`.
Refactor `workflow_execute_verification` to build spec from node `data.verification` via `normalize_verification_spec`, then call `run_verification`.
Refactor `tree_server._handle_verify` to use the same path (import from verify_runner or via workflow_mcp — prefer direct import to avoid circular deps).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_verify_runner.py ai-workflow/tests/test_workflow_mcp.py ai-workflow/tests/test_tree_server.py -v`
Expected: PASS (0 regressions).

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/project_tree/verify_runner.py ai-workflow/scripts/workflow_mcp.py ai-workflow/scripts/tree_server.py ai-workflow/tests/test_verify_runner.py
git commit -m "feat(verify): add shared verify_runner harness and refactor MCP/REST callers"
```

---

### Task 3: Pattern Fingerprinting & Decay Scanner

**Files:**
- Modify: `ai-workflow/scripts/project_tree/patterns.py`
- Create: `ai-workflow/scripts/project_tree/decay.py`
- Modify: `ai-workflow/scripts/project_tree/cli.py`
- Create: `ai-workflow/tests/test_decay.py`

**Interfaces:**
- Consumes: Composed project tree, filesystem state, optional `changed_files: list[Path]`
- Produces:
  - `compute_pattern_fingerprint(node, tree) -> str` — SHA-256 hex of sorted `rel_path:content_hash` for all files matching `data.pattern`
  - `scan_decay(project, *, dry_run=False, changed_files=None) -> dict` — `{scanned, decayed, refreshed, nodes: [...]}`

**Decay rules:**
1. Only consider nodes with `status == "verified_strong"` and non-empty `data.pattern`.
2. Compare stored `data.verification.fingerprint` (if any) to current fingerprint.
3. If fingerprint unchanged → skip.
4. If fingerprint changed:
   - If node has verification spec → run via `verify_runner.run_verification`.
   - Pass → update `fingerprint`, `last_run_sha` (git HEAD), `last_exit_code=0`, keep `verified_strong`.
   - Fail or no verification → set `status` to `decayed_unverified`, set `data.decayed=True`, record `decay_reason`.
5. `dry_run=True` reports actions without writing YAML.

CLI: `project_tree decay-scan <project> [--dry-run]`

- [ ] **Step 1: Write failing tests for fingerprint and decay scan**

In `ai-workflow/tests/test_decay.py`:
- Fingerprint stable across two reads of unchanged files.
- Fingerprint changes when file content changes.
- `verified_strong` node with changed fingerprint + failing command → `decayed_unverified`.
- `verified_strong` node with changed fingerprint + passing command → stays strong, fingerprint updated.
- `dry_run` does not write files.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_decay.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement fingerprint and decay scanner**

In `patterns.py`: add `resolve_pattern_files(node, tree) -> list[Path]` and `compute_pattern_fingerprint(node, tree) -> str`.
In `decay.py`: implement `scan_decay` with rules above; persist via `model.save_tree` / fragment save as needed.
In `cli.py`: add `decay-scan` subcommand.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_decay.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/project_tree/patterns.py ai-workflow/scripts/project_tree/decay.py ai-workflow/scripts/project_tree/cli.py ai-workflow/tests/test_decay.py
git commit -m "feat(decay): add pattern fingerprinting and verified_strong auto-decay scanner"
```

---

### Task 4: Git Hook, MCP Tool, REST Endpoint & Cockpit Scan Trigger

**Files:**
- Create: `ai-workflow/scripts/decay_hook.py`
- Modify: `ai-workflow/scripts/project_tree/cli.py`
- Modify: `ai-workflow/scripts/workflow_mcp.py`
- Modify: `ai-workflow/scripts/tree_server.py`
- Modify: `ai-workflow/tools/tree-viewer/index.html`
- Modify: `ai-workflow/tools/tree-viewer/app.js`
- Modify: `ai-workflow/tests/test_tree_server.py`
- Modify: `ai-workflow/tests/test_cockpit_e2e.py`

**Interfaces:**
- CLI: `project_tree install-decay-hook` writes `.git/hooks/post-commit` snippet calling `python3 ai-workflow/scripts/decay_hook.py`
- MCP: `workflow_decay_scan(project, dry_run=False)` → same result dict as `scan_decay`
- REST: `POST /api/decay-scan` body `{"project": "...", "dry_run": false}` → JSON result
- Cockpit: "Scan Decay" button in verify widget area triggers POST, logs results to activity console

- [ ] **Step 1: Write failing tests for hook, MCP, REST, and E2E**

- `test_decay.py`: test `decay_hook.py` main with mocked `scan_decay` invocation.
- `test_workflow_mcp.py`: test `workflow_decay_scan` tool registered and returns scan result.
- `test_tree_server.py`: test `POST /api/decay-scan` returns 200 with `scanned` key.
- `test_cockpit_e2e.py`: test decay-scan endpoint over real subprocess server.

- [ ] **Step 2: Run tests to verify they fail**

Run targeted new tests — Expected: FAIL.

- [ ] **Step 3: Implement hook installer, MCP tool, REST endpoint, Cockpit button**

- `decay_hook.py`: resolve changed files from `git diff-tree` for latest commit, call `scan_decay` for each discovered project (or all projects if simpler for v1).
- `install-decay-hook` CLI: append or write hook script; print install path.
- Register MCP tool; add REST handler; add Cockpit button + fetch handler.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: 100% PASS, 0 regressions.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/decay_hook.py ai-workflow/scripts/project_tree/cli.py ai-workflow/scripts/workflow_mcp.py ai-workflow/scripts/tree_server.py ai-workflow/tools/tree-viewer/index.html ai-workflow/tools/tree-viewer/app.js ai-workflow/tests/test_decay.py ai-workflow/tests/test_workflow_mcp.py ai-workflow/tests/test_tree_server.py ai-workflow/tests/test_cockpit_e2e.py
git commit -m "feat(decay): wire post-commit hook, MCP/REST decay scan, and Cockpit trigger"
```
