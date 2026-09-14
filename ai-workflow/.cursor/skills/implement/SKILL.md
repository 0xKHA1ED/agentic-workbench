---
name: implement
description: Autonomously execute code changes strictly against an approved scope contract until all VERIFY assertions pass.
disable-model-invocation: false
---

# Autonomous Implementation Protocol (`/implement`)

Autonomously execute code changes strictly against an approved scope contract until all VERIFY assertions pass. You are bounded strictly by `IN` and `OUT`.

Announce: "Using implement skill."

## Mission

Once a scope contract is approved, implementation becomes **pure execution against falsifiable gates**. The agent is never permitted to declare victory or guess that code works — every change must be verified through automated execution, bounded by contract limits, and verified via `workflow_execute_verification`.

---

## The 4-Phase Protocol

### Phase 1: Contract Intake & Bounds Verification

1. **Intake Approved Contract**:
   - Fetch the node state via `workflow_get_node` or read the approved contract: `specs/<node-id>.md`.
   - Load `workflow_get_constitution` — MUST principles are non-negotiable; do not contradict them.
   - Verify node status is `spec_approved`. If the contract is not approved or is still in draft (`weak`, `spec_ready`), **STOP immediately** and prompt the human partner for approval.
2. **Analyze gate** (`workflow_get_node` → `analyze.status`, or `workflow_analyze_context`):
   - Status MUST be `complete` or `skipped` (persisted at `<project>/analyze/<node-id>.analyze.json`).
   - If status is **missing** or **`in_progress`**, **STOP**. Tell the user to run `/spec-analyze` (`workflow_analyze_run` then `workflow_analyze_complete`) or skip (`workflow_analyze_skip`).
   - **CRITICAL findings do not hard-block** after complete or skip. Report them; proceed unless the user stops.
3. **Bounds Verification**:
   - Catalog the strict contract boundaries:
     - **IN Scope**: Whitelisted files, directories, and components permitted to be modified.
     - **OUT Scope**: Explicitly forbidden files, adjacent systems, and third-party dependencies that must remain untouched.
     - **MUST**: Positive behavioral invariants that must be satisfied.
     - **MUST NOT**: Critical red lines that must never be crossed.
     - **VERIFY**: Falsifiable checks with executable commands.
     - If `data.plan` is set, read that HOW file (`plans/<node-id>.plan.md`) for file map / sequencing. The contract VERIFY still gates DONE; do not treat the plan as additional MUST.
4. **Requirements checklist gate (read-only)**:
   - Call `workflow_checklist_status` (`project`, `node_id`). CLI fallback: `python3 scripts/spec_checklist.py status <project> <node_id> --json`.
   - Treat markers as **read-only**. Count checked vs unchecked. **Do not** edit checklist files or toggle `[ ]` / `[x]`.
   - `[x]` on a custom checklist means the reviewer accepted **requirements quality**, not that implementation is done.
   - If `blocks_implement` is true — especially **unchecked custom** checklists (`checklists/<node-id>/*.md` other than `requirements.md`) — **STOP** and show the counts table. Ask: "Some checklists have unchecked items. Proceed with implementation anyway? (yes/no)". Wait for the user.
   - If no checklist directory exists, continue (optional quality step).
5. **Task-breakdown scope (optional)**:
   - Resolve `tasks/<node-id>.md` via MCP `workflow_tasks_paths` or:
     ```bash
     python3 scripts/task_breakdown.py paths <project> <node_id> --json
     ```
   - If the file is **missing**, continue with contract-only implement (do not block). Suggest `/task-breakdown` for large nodes.
   - Parse phase markers `<!-- task-phase: id=<id> index=N -->` and checklist lines `- [ ] T00N`.
   - If the user scoped the run (`phase 2`, `setup`, `foundational`, `T001-T004`):
     ```bash
     python3 scripts/task_breakdown.py scope <project> <node_id> --phase <id> --json
     python3 scripts/task_breakdown.py scope <project> <node_id> --tasks T001-T004 --json
     ```
     Execute **only** incomplete tasks in that scope. Do not start later phases.
   - Unscoped: complete phases in order (Setup → Foundational → claim stories → Polish). Foundational **blocks** stories.
   - Mark finished **tasks.md** checkboxes `- [x]`. Do **not** change requirements-checklist files.
   - Contract **IN / OUT** still win if a task path is out of scope.
   - `[P]` tasks may proceed together when they touch different files; same-file tasks stay sequential.

---

### Phase 2: Surgical Modification

1. **Strict Scope Confinement**:
   - Modify **ONLY** files within the declared `IN` scope and matching `data.pattern`.
   - Never refactor adjacent files, reorganize directories, or introduce cosmetic cleanups outside scope.
2. **No Speculative Additions**:
   - Implement only the minimal, robust code necessary to satisfy the `GOAL` and pass `VERIFY`.
   - Do not add unrequested helpers, speculative abstractions, or future-proofing flags.
3. **Respect Red Lines**:
   - Cross-check every proposed edit against the `MUST NOT` list prior to applying changes.

---

### Phase 3: The VERIFY Walk (Self-Correction Loop)

Execute and validate every assertion specified in the contract's `VERIFY` section.

For each check in `VERIFY`:
1. **Execute Verification Assertion**:
   Call `workflow_execute_verification` directly via MCP:
   ```json
   {
     "project": "<project>",
     "node_id": "<node_id>"
   }
   ```
2. **Handle Failure (Self-Correction)**:
   If the check FAILS (`status: "failed"` or `exit_code != 0`):
   - Inspect `stdout`, `stderr`, exception traces, and failure outputs.
   - Formulate a surgical, targeted fix strictly within `IN` bounds.
   - Apply the fix to source code.
   - Re-execute the verification via `workflow_execute_verification`.
   - **Limit**: Maximum **3 self-correction iterations**. If the assertion continues to fail after 3 attempts, **STOP** immediately and report the specific blocker, failing assertion, and error trace to the human partner.
3. **Handle Success**:
   If the check PASSES (`status: "passed"` and `exit_code == 0`):
   - Record the passing exit code, execution duration, and stdout evidence.

---

### Phase 4: Promotion & Closure

1. **Node Status Promotion**:
   When 100% of automated `VERIFY` checks pass:
   - Propose promoting the node to `verified_strong` via `workflow_propose_tree_mutation`:
     ```json
     {
       "project": "<project>",
       "target_node_id": "<node_id>",
       "operation": "set_status",
       "payload": {
         "status": "verified_strong"
       }
     }
     ```
2. **Execution Summary**:
   Output a concise, factual completion report:
   - **Files Modified**: List of touched files and diff stats (+/- lines).
   - **Verification Results**: Exit codes, execution duration, and passing test summary from `workflow_execute_verification`.
   - **Manual Sensory Verification**: Any non-automated user acceptance steps remaining from the contract (e.g. visual UI checks).

---

## Anti-Patterns (Strictly Forbidden)

- **Implementing Without Approval**: Touching code when status is not `spec_approved`.
- **Scope Creep & Boundary Violations**: Modifying files in `OUT` or editing unapproved adjacent modules.
- **Unverified Victory**: Declaring a task complete or node resolved without running `workflow_execute_verification` and getting a clean exit code 0.
- **Infinite Self-Correction**: Attempting more than 3 repair cycles without stopping to consult the human partner.
- **Bypassing Red Lines**: Violating a `MUST NOT` directive to make a test pass.
- **Skipping analyze**: Starting Phase 2 while analyze status is missing or `in_progress`.
- **Blocking on CRITICAL after complete/skip**: Do not hard-block `/implement` solely because findings contain CRITICAL once status is complete or skipped.
- **Unscoped Drift**: When the user named a phase or `T00N` range, implementing tasks outside that `<!-- task-phase -->` scope.
- **Self-approving checklists**: Marking `[x]` on requirements or custom checklists during implement. Checkbox state is user-only; implement only counts.
