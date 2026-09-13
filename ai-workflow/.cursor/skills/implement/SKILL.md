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
   - Verify node status is `spec_approved`. If the contract is not approved or is still in draft (`weak`, `spec_ready`), **STOP immediately** and prompt the human partner for approval.
2. **Bounds Verification**:
   - Catalog the strict contract boundaries:
     - **IN Scope**: Whitelisted files, directories, and components permitted to be modified.
     - **OUT Scope**: Explicitly forbidden files, adjacent systems, and third-party dependencies that must remain untouched.
     - **MUST**: Positive behavioral invariants that must be satisfied.
     - **MUST NOT**: Critical red lines that must never be crossed.
     - **VERIFY**: Falsifiable checks with executable commands.

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
