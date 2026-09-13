# AI Workflow v2 Phase 1: Native Cursor MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 of AI Workflow v2: build a zero-dependency stdio Model Context Protocol (MCP) server (`workflow_mcp.py`) exposing the core workflow tools, configure `.cursor/mcp.json`, update existing skills to remove terminal ceremony, and author the missing `/understand` and `/implement` skills.

**Architecture:** Build a clean JSON-RPC 2.0 stdio MCP server in `ai-workflow/scripts/workflow_mcp.py` that interfaces with `project_tree.model`, `project_tree.ops`, and `spec_discovery`. Expose 5 native MCP tools (`workflow_orient`, `workflow_get_node`, `workflow_propose_tree_mutation`, `workflow_stage_contract_claims`, `workflow_execute_verification`). Configure Cursor MCP settings and update `.cursor/skills/` to empower agents to propose, triage, and verify directly in the IDE without terminal context switches.

**Tech Stack:** Python 3.10+, stdlib `json`, `sys`, `subprocess`, `unittest`, PyYAML 6.0+.

**Spec:** `ai-workflow/meta/docs/ARCHITECTURE-V2-PROPOSAL.md` (Sections 6, 9, 10, 11 Phase 1)

## Global Constraints

- Zero third-party dependencies beyond PyYAML (`PyYAML>=6.0`). Standard library only (`json`, `sys`, `subprocess`, `unittest`, `pathlib`).
- The MCP server must communicate over standard I/O (stdio) using JSON-RPC 2.0 messages (newline-delimited JSON). All logging/debug output must go to `sys.stderr` so stdout remains pure JSON-RPC.
- The MCP tool schemas must match Section 6 of `ARCHITECTURE-V2-PROPOSAL.md` (`workflow_orient`, `workflow_get_node`, `workflow_propose_tree_mutation`, `workflow_stage_contract_claims`, `workflow_execute_verification`).
- All existing CLI commands must remain 100% backward-compatible.
- All existing 74 unit/E2E tests must continue to pass with 0 regressions.

---

### Task 1: Core MCP Protocol Server & Dispatch Engine

**Files:**
- Create: `ai-workflow/scripts/workflow_mcp.py`
- Create: `ai-workflow/tests/test_workflow_mcp.py`

**Interfaces:**
- Consumes: JSON-RPC 2.0 requests over stdin
- Produces: JSON-RPC 2.0 responses over stdout for `initialize`, `notifications/initialized`, `ping`, `tools/list`, and `tools/call`.

- [ ] **Step 1: Write failing unit test for MCP protocol transport and dispatcher**

In `ai-workflow/tests/test_workflow_mcp.py`:
- Test `initialize`: returns server protocol version (`2024-11-05`), capabilities (`tools`), and server info (`ai-workflow`, `2.0.0`).
- Test `ping`: returns empty result `{}`.
- Test `tools/list`: returns array of registered tools.
- Test error handling for malformed JSON, unknown methods, and missing parameters.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'workflow_mcp'`).

- [ ] **Step 3: Implement `MCPServer` in `ai-workflow/scripts/workflow_mcp.py`**

Implement:
- Standard JSON-RPC 2.0 request parsing and response formatting.
- Method routing for `initialize`, `notifications/initialized`, `ping`, `tools/list`, and `tools/call`.
- Stdio message loop (`run_stdio_server`).
- Tool registry decorator `@register_tool(name, description, input_schema)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/workflow_mcp.py ai-workflow/tests/test_workflow_mcp.py
git commit -m "feat(mcp): implement core JSON-RPC stdio MCP server engine"
```

---

### Task 2: Implement Read Tools (`workflow_orient` & `workflow_get_node`)

**Files:**
- Modify: `ai-workflow/scripts/workflow_mcp.py`
- Modify: `ai-workflow/tests/test_workflow_mcp.py`

**Interfaces:**
- Consumes: `project_tree.model`, `project_tree.fragments`
- Produces: MCP tools `workflow_orient` and `workflow_get_node`

- [ ] **Step 1: Write unit tests for `workflow_orient` and `workflow_get_node`**

In `ai-workflow/tests/test_workflow_mcp.py`:
- Test `workflow_orient` on `meta` with filter `weak`, verifying it returns node count, list of weak nodes, and pending proposals status.
- Test `workflow_orient` with filter `all` and unknown project error handling.
- Test `workflow_get_node` returning complete details (`title`, `kind`, `status`, `data.pattern`, `data.pain`, `data.contract`, `data.claims`) for existing node.
- Test `workflow_get_node` error when node is not found.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: FAIL (`tools/call` for `workflow_orient` returns unknown tool).

- [ ] **Step 3: Implement `workflow_orient` and `workflow_get_node`**

In `ai-workflow/scripts/workflow_mcp.py`:
- Register `workflow_orient`: loads composed tree for project, scans nodes, collects weak/decayed nodes and pending proposals, returns formatted markdown and structured JSON.
- Register `workflow_get_node`: finds target node in tree, extracts all attributes, returns clean structured payload.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/workflow_mcp.py ai-workflow/tests/test_workflow_mcp.py
git commit -m "feat(mcp): add workflow_orient and workflow_get_node tools"
```

---

### Task 3: Implement Mutation & Execution Tools (`workflow_propose_tree_mutation`, `workflow_stage_contract_claims`, `workflow_execute_verification`)

**Files:**
- Modify: `ai-workflow/scripts/workflow_mcp.py`
- Modify: `ai-workflow/tests/test_workflow_mcp.py`

**Interfaces:**
- Consumes: `project_tree.ops`, `project_tree.cli`, `project_tree.model`
- Produces: MCP tools `workflow_propose_tree_mutation`, `workflow_stage_contract_claims`, `workflow_execute_verification`

- [ ] **Step 1: Write unit tests for mutation, claims staging, and verification execution**

In `ai-workflow/tests/test_workflow_mcp.py`:
- Test `workflow_propose_tree_mutation`: tests `set_data` (e.g. setting `pain`), `add_child`, and `set_status`, verifying `.proposed` file is staged with diff returned.
- Test `workflow_stage_contract_claims`: tests writing atomic claims JSON file to `claims/<node_id>.json`, verifying schema validation and non-falsifiable claim rejection.
- Test `workflow_execute_verification`: executes a command verification check, returns exit code, stdout, and execution status.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: FAIL (tools not yet registered).

- [ ] **Step 3: Implement the mutation and verification tools**

In `ai-workflow/scripts/workflow_mcp.py`:
- `workflow_propose_tree_mutation`: stages proposal non-interactively, computes unified diff, and returns staged status.
- `workflow_stage_contract_claims`: validates claims against schema, writes `claims/<node_id>.json`.
- `workflow_execute_verification`: runs verification command via `subprocess.run`, captures returncode, stdout, stderr, and timings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_workflow_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/workflow_mcp.py ai-workflow/tests/test_workflow_mcp.py
git commit -m "feat(mcp): add tree mutation, claims staging, and verification execution tools"
```

---

### Task 4: Cursor IDE MCP Configuration & Existing Skill Updates

**Files:**
- Create: `.cursor/mcp.json`
- Create: `ai-workflow/.cursor/mcp.json`
- Modify: `ai-workflow/.cursor/skills/project-tree/SKILL.md`
- Modify: `ai-workflow/.cursor/skills/spec-discovery/SKILL.md`
- Modify: `ai-workflow/.cursor/skills/scope-contract/SKILL.md`

**Interfaces:**
- Consumes: `ai-workflow/scripts/workflow_mcp.py`
- Produces: Cursor MCP configuration and auto-invoking skills

- [ ] **Step 1: Create `.cursor/mcp.json` and `ai-workflow/.cursor/mcp.json`**

Configure standard stdio server:
```json
{
  "mcpServers": {
    "ai-workflow": {
      "command": "python3",
      "args": ["ai-workflow/scripts/workflow_mcp.py"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

- [ ] **Step 2: Update `project-tree/SKILL.md`**

Update skill instructions:
- Agents call `workflow_propose_tree_mutation` via MCP directly instead of outputting shell commands for the user to copy-paste.
- Add guidance on `workflow_get_node` for inspecting node context.

- [ ] **Step 3: Update `spec-discovery/SKILL.md` and `scope-contract/SKILL.md`**

- In `spec-discovery/SKILL.md`: agents stage claims via `workflow_stage_contract_claims`.
- In `scope-contract/SKILL.md`: add executable assertion syntax (`check_type`, `command`, `pytest`) to `VERIFY` items.

- [ ] **Step 4: Run existing test suite to ensure no breakage**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .cursor/mcp.json ai-workflow/.cursor/mcp.json ai-workflow/.cursor/skills/
git commit -m "feat(mcp): add cursor mcp configuration and adapt existing skills"
```

---

### Task 5: Author Hollow L1 Skills (`understand` & `implement`) & Full Integration Pass

**Files:**
- Create: `ai-workflow/.cursor/skills/understand/SKILL.md`
- Create: `ai-workflow/.cursor/skills/implement/SKILL.md`
- Modify: `ai-workflow/tests/test_workflow_mcp.py`

**Interfaces:**
- Consumes: MCP tools (`workflow_orient`, `workflow_get_node`, `workflow_propose_tree_mutation`, `workflow_execute_verification`)
- Produces: `/understand` and `/implement` skills + End-to-end integration test

- [ ] **Step 1: Author `understand` skill**

Create `ai-workflow/.cursor/skills/understand/SKILL.md` based on Section 9 of the proposal:
- Pain ingestion protocol.
- Autonomous read-only code exploration.
- Root cause hypothesis formulation.
- Tree node mutation calling `workflow_propose_tree_mutation` to record `data.pain`.

- [ ] **Step 2: Author `implement` skill**

Create `ai-workflow/.cursor/skills/implement/SKILL.md` based on Section 9 of the proposal:
- Contract intake & bounds verification (`IN` / `OUT`).
- Surgical modification strictly bounded by `IN` scope.
- Autonomous VERIFY walk using `workflow_execute_verification`.
- Promotion to `verified_strong` on passing verification.

- [ ] **Step 3: Add full pipeline integration test in `test_workflow_mcp.py`**

Test the entire MCP flow through stdio subprocess:
1. Initialize server.
2. Call `workflow_orient`.
3. Call `workflow_get_node`.
4. Call `workflow_propose_tree_mutation`.
5. Call `workflow_stage_contract_claims`.
6. Call `workflow_execute_verification`.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: 100% PASS with 0 failures across all unit, MCP, and E2E CLI tests.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/.cursor/skills/understand/ ai-workflow/.cursor/skills/implement/ ai-workflow/tests/
git commit -m "feat(skills): author understand and implement skills and add mcp e2e pipeline test"
```
