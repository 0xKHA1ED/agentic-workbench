# AI Workflow v2 Phase 2: Web Cockpit & High-Speed Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the passive `tree-viewer` into a high-speed, bidirectional developer Cockpit HUD with real-time SSE updates, REST endpoints for proposal apply/reject, claims triage, verification execution, and sub-second Vim-style keyboard navigation (`J`/`K`/`Y`/`N`).

**Architecture:** Upgrade `tree_server.py` from a static file server into a lightweight REST + Server-Sent Events (SSE) server using pure Python standard library (`http.server`, `threading`, `json`). Rewrite `tools/tree-viewer/` (`index.html`, `styles.css`, `app.js`) into a responsive 2-column Cockpit flight deck with live SSE reconnect, search/filter, 1-click proposal review, and keyboard triage. Lift the single-pending proposal bottleneck to support independent concurrent fragment proposals.

**Tech Stack:** Python 3.10+ stdlib (`http.server.ThreadingHTTPServer`, `threading`, `json`, `subprocess`, `pathlib`, `unittest`), PyYAML, Vanilla ES6+ JavaScript, CSS3 (zero external frontend frameworks, zero third-party backend packages).

**Spec:** Section 6 (Interaction Model & Cockpit HUD), Section 8 (Automation), and Section 11 (Phase 2) of `ai-workflow/meta/docs/ARCHITECTURE-V2-PROPOSAL.md`.

## Global Constraints

- Zero third-party dependencies beyond PyYAML (`PyYAML>=6.0`). Standard library only.
- The web server must communicate over HTTP/1.1 on `127.0.0.1:8765` (or user-specified port) with CORS disabled or restricted to localhost.
- Server-Sent Events (SSE) must stream at `/api/events/<project>` without external websocket libraries.
- Existing CLI commands (`show`, `compose`, `list-fragments`, `validate-patterns`, `propose`, `apply`, `reject`) and MCP tools must remain 100% backward-compatible.
- All existing 123 tests must continue to pass with 0 regressions.

---

### Task 1: Lift Fragment Pending Bottleneck & Multi-Proposal Support

**Files:**
- Modify: `ai-workflow/scripts/project_tree/model.py`
- Modify: `ai-workflow/scripts/project_tree/cli.py`
- Modify: `ai-workflow/tests/test_model.py`
- Modify: `ai-workflow/tests/test_ops.py`

**Interfaces:**
- Consumes: `model.list_pending_proposals`, `fragments.resolve_fragment_path`
- Produces: `get_pending_proposal_diff(project, fragment_rel)`, `apply_pending_proposal(project, fragment_rel)`, `reject_pending_proposal(project, fragment_rel)` in `model.py` / `ops.py`.
- Behavior: Proposing a mutation for fragment `A` does not block proposing for fragment `B`. Only a pending proposal targeting the exact same fragment (or root) blocks until resolved.

- [ ] **Step 1: Write failing tests for fragment-independent pending proposals**

In `ai-workflow/tests/test_model.py`, add tests verifying:
- Two distinct fragments (`fragments/alpha.yaml` and `fragments/beta.yaml`) can have `.proposed` files simultaneously.
- `apply_pending_proposal` applies only the specified fragment without touching the other.
- `reject_pending_proposal` unlinks only the specified fragment's `.proposed` file.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_model.py -v`
Expected: FAIL on new proposal functions not found or bottleneck check.

- [ ] **Step 3: Implement fragment-scoped proposal isolation and programmatic apply/reject**

In `ai-workflow/scripts/project_tree/model.py` and `cli.py`:
- Refactor `_propose` in `cli.py` to only block if `_pending_path(project, fragment_rel).exists()`.
- Export clean helper functions in `model.py`: `get_pending_proposal_diff(project, fragment_rel)`, `apply_pending_proposal(project, fragment_rel)`, and `reject_pending_proposal(project, fragment_rel)`.
- Use these helpers in `cli.py`'s `_apply_target` and `_reject_target`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_model.py ai-workflow/tests/test_ops.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/project_tree/model.py ai-workflow/scripts/project_tree/cli.py ai-workflow/tests/test_model.py ai-workflow/tests/test_ops.py
git commit -m "feat(tree): lift single-pending bottleneck and add programmatic apply/reject helpers"
```

---

### Task 2: Upgraded Cockpit REST API Engine in `tree_server.py`

**Files:**
- Modify: `ai-workflow/scripts/tree_server.py`
- Modify: `ai-workflow/tests/test_tree_server.py`

**Interfaces:**
- Consumes: `model.apply_pending_proposal`, `model.reject_pending_proposal`, `workflow_mcp.workflow_propose_tree_mutation`, `workflow_mcp.workflow_execute_verification`
- Produces REST endpoints:
  - `GET /api/proposals/<project>` -> `{"proposals": [{"target": "...", "path": "...", "diff": "..."}]}`
  - `POST /api/proposals/apply` (body: `{"project": "...", "fragment": "..."}`) -> `{"status": "applied"}`
  - `POST /api/proposals/reject` (body: `{"project": "...", "fragment": "..."}`) -> `{"status": "rejected"}`
  - `GET /api/claims/<project>/<node_id>` -> claims JSON
  - `POST /api/claims/triage` (body: `{"project": "...", "node_id": "...", "claim_id": "...", "decision": "approved"|"rejected"}`) -> updated status
  - `POST /api/verify` (body: `{"project": "...", "node_id": "..."}`) -> verification execution result

- [ ] **Step 1: Write failing tests for REST endpoints**

In `ai-workflow/tests/test_tree_server.py`, add tests covering:
- `GET /api/proposals/<project>` returning staged diffs.
- `POST /api/proposals/apply` applying proposal and returning HTTP 200.
- `POST /api/proposals/reject` discarding proposal.
- `GET /api/claims/<project>/<node_id>` reading `claims/<node_id>.json`.
- `POST /api/claims/triage` modifying claim status.
- `POST /api/verify` calling verification execution.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: FAIL (404/405 on new endpoints).

- [ ] **Step 3: Implement REST handlers in `tree_server.py`**

In `ai-workflow/scripts/tree_server.py`:
- Add `do_POST` dispatch logic in `TreeHandler` to parse JSON bodies (`self.rfile.read(content_length)`).
- Implement endpoint handlers for proposals apply/reject, claims triage, and verification.
- Return structured JSON responses with proper status codes (200, 400, 404).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/tree_server.py ai-workflow/tests/test_tree_server.py
git commit -m "feat(server): add REST endpoints for proposals, claims triage, and verification"
```

---

### Task 3: Real-Time SSE (Server-Sent Events) Stream in `tree_server.py`

**Files:**
- Modify: `ai-workflow/scripts/tree_server.py`
- Modify: `ai-workflow/tests/test_tree_server.py`

**Interfaces:**
- Consumes: Project directory file watcher (tracking mtimes of `nodes.yaml`, `nodes.yaml.proposed`, `fragments/`, `claims/`)
- Produces: `GET /api/events/<project>` SSE stream emitting `event: tree_changed\ndata: {"project": "..."}\n\n`

- [ ] **Step 1: Write failing tests for SSE endpoint**

In `ai-workflow/tests/test_tree_server.py`, add a test that connects to `GET /api/events/<project>`, modifies a file in a temporary project directory, and verifies that an SSE event formatted as `event: ...\ndata: ...\n\n` is streamed over the HTTP connection.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: FAIL (SSE endpoint not handled).

- [ ] **Step 3: Implement SSE streaming in `tree_server.py`**

In `ai-workflow/scripts/tree_server.py`:
- When request path is `GET /api/events/<project>`, send headers:
  `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`.
- Maintain a subscriber registry or change-detection loop with 0.5s polling interval on project directory mtime hash.
- Stream events when tree, fragments, or proposals change.
- Handle client disconnect cleanly without leaking threads.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest ai-workflow/tests/test_tree_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-workflow/scripts/tree_server.py ai-workflow/tests/test_tree_server.py
git commit -m "feat(server): implement real-time SSE file change stream"
```

---

### Task 4: Cockpit HUD Layout & Styling (`index.html` & `styles.css`)

**Files:**
- Modify: `ai-workflow/tools/tree-viewer/index.html`
- Modify: `ai-workflow/tools/tree-viewer/styles.css`

**Interfaces:**
- Consumes: Modern responsive CSS layout and semantic HTML structure
- Produces: HUD flight deck layout:
  - Header: Project switcher, health bar (% verified), status filter chips (`All`, `Weak`, `Stale`, `Strong`), search input, and keyboard cheat-sheet toggle.
  - Left Pane: Scrollable tree hierarchy with keyboard focus outline and status badges.
  - Right Pane:
    - Node inspector (Title, ID, Kind, Status, Pattern, Pain, Contracts).
    - Pending Proposals Banner with diff view and 1-click Apply/Reject.
    - Active Claims Triage Box (falsifiable claims list with `[Y]` / `[N]` badges).
    - Verification Console Widget with "Run Verification" trigger and execution logs.
  - Bottom: Console activity stream.

- [ ] **Step 1: Update `index.html` with Cockpit HUD elements**

Rebuild `index.html` to declare the structured layout elements (search input, filter toggles, health meter, 2-column workspace, triage box, verification runner, and console).

- [ ] **Step 2: Update `styles.css` with engineering HUD styling**

Implement dark mode palette (`#0d1117`, `#161b22`, `#21262d`), high-contrast status colors (`#238636` for strong, `#da3633` for weak, `#d29922` for stale), clean monospaced code blocks, and keyboard shortcut badges.

- [ ] **Step 3: Verify static rendering**

Verify HTML/CSS syntax and check that `tree_server.py` serves static assets properly.

- [ ] **Step 4: Commit**

```bash
git add ai-workflow/tools/tree-viewer/index.html ai-workflow/tools/tree-viewer/styles.css
git commit -m "feat(viewer): implement Cockpit HUD layout and styling"
```

---

### Task 5: Reactive Frontend Logic & Vim-Speed Keyboard Triage Engine (`app.js`)

**Files:**
- Modify: `ai-workflow/tools/tree-viewer/app.js`

**Interfaces:**
- Consumes: REST API (`/api/projects`, `/api/tree/<p>`, `/api/proposals/<p>`, `/api/proposals/apply`, `/api/proposals/reject`, `/api/claims/<p>/<n>`, `/api/claims/triage`, `/api/verify`) and SSE (`/api/events/<p>`).
- Produces: Keyboard navigation & triage loop:
  - `J`/`K`: Move selection between tree nodes or active claims.
  - `Y`/`N`: Approve / reject active claim or proposal.
  - `A`: Approve all claims.
  - `Space`: Expand/collapse tree node.
  - Real-time search filter filtering tree nodes by title, ID, or pattern.
  - Live SSE connection auto-updating view when backend files change.

- [ ] **Step 1: Implement state management and REST API client in `app.js`**

Add state object (`currentProject`, `selectedNodeId`, `selectedClaimIndex`, `filterMode`, `searchQuery`, `proposals`, `claims`). Add fetch wrappers for `/api/proposals/apply`, `/api/proposals/reject`, `/api/claims/triage`, and `/api/verify`.

- [ ] **Step 2: Implement keyboard navigation and triage hotkeys**

Bind `keydown` event handler (ignoring when typing in `<input>`):
- `J` / `ArrowDown`: select next visible node or claim.
- `K` / `ArrowUp`: select previous visible node or claim.
- `Y`: approve selected claim/proposal and advance.
- `N`: reject selected claim/proposal and advance.
- `A`: approve all visible claims.
- `Space` / `Enter`: toggle expansion.

- [ ] **Step 3: Implement SSE auto-refresh**

Connect `new EventSource('/api/events/' + encodeURIComponent(project))` with auto-reconnect logic to reload tree and proposals on `tree_changed` events.

- [ ] **Step 4: Commit**

```bash
git add ai-workflow/tools/tree-viewer/app.js
git commit -m "feat(viewer): implement reactive frontend logic and vim keyboard triage engine"
```

---

### Task 6: End-to-End Cockpit Integration Test Suite & Full System Verification

**Files:**
- Create: `ai-workflow/tests/test_cockpit_e2e.py`
- Modify: `ai-workflow/tests/test_tree_server.py`

**Interfaces:**
- Consumes: Subprocess execution of `ai-workflow/scripts/tree_server.py`
- Produces: Automated E2E verification of HTTP REST endpoints, SSE streaming, proposal lifecycle, and claims triage over real socket connections.

- [ ] **Step 1: Write `ai-workflow/tests/test_cockpit_e2e.py`**

Test the running server subprocess:
1. Start server on dynamic free port (`127.0.0.1:0` or ephemeral test port).
2. Fetch `/api/projects`.
3. Fetch `/api/tree/<project>`.
4. Connect to `/api/events/<project>`.
5. Propose tree mutation and verify `/api/proposals/<project>` returns diff.
6. Call `POST /api/proposals/apply` and verify proposal is applied to tree.
7. Stage claims and triage via `POST /api/claims/triage`.
8. Call `POST /api/verify` and verify execution results.

- [ ] **Step 2: Run new E2E test suite**

Run: `python3 -m unittest ai-workflow/tests/test_cockpit_e2e.py -v`
Expected: PASS.

- [ ] **Step 3: Run full repository test suite**

Run: `python3 -m unittest discover -s ai-workflow/tests -v`
Expected: 100% PASS with 0 failures, 0 errors across all unit, MCP, CLI, and Cockpit tests.

- [ ] **Step 4: Commit**

```bash
git add ai-workflow/tests/test_cockpit_e2e.py ai-workflow/tests/test_tree_server.py
git commit -m "test(cockpit): add end-to-end integration tests for web cockpit and rest/sse engine"
```
