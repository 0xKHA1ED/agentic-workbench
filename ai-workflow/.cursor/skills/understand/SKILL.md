---
name: understand
description: Autonomous AST exploration, stack trace ingestion, git blame analysis, and automated pain crystallization into tree nodes.
disable-model-invocation: false
---

# Autonomous Pain Exploration & Understanding Protocol (`/understand`)

Take messy human frustration, bug reports, stack traces, or half-formed ideas and transform them into **crystallized node pain and architectural decomposition** across the codebase without writing speculative implementation code.

Announce: "Using understand skill."

## Mission

When an engineer encounters unexpected behavior, performance degradation, or complex bugs, jumping straight into code modifications causes thrash and regressions. 

The `/understand` skill establishes a strictly **read-only** discovery ritual: explore the codebase, trace symbols and git history, formulate a falsifiable root-cause hypothesis, crystallize the pain into the project tree via MCP (`workflow_propose_tree_mutation`), and obtain human confirmation before any specification or coding begins.

---

## The 5-Phase Protocol

### Phase 1: Pain Ingestion

1. **Ingest Raw Intent**:
   - Capture user bug descriptions, error logs, reproduction steps, or unexpected system outputs (e.g. `/understand Marbles tunnel through dynamic wedges in Tik simulation when speed exceeds 1200px/s`).
2. **Context Resolution**:
   - Determine target project and node using `workflow_orient` or `workflow_get_node`.
   - If no node exists yet, identify the parent group where new work should attach.
3. **Quantify Symptoms**:
   - Extract measurable indicators: error messages, stack trace lines, performance thresholds, frequency, or reproduction triggers.

---

### Phase 2: Autonomous Code Exploration (Read-Only)

Execute targeted read operations across the codebase. **Zero code modifications are permitted during this phase.**

1. **Symbol & AST Search**:
   - Search for key classes, functions, interfaces, and state structures linked to the reported pain.
   - Trace callers, callees, and data flow pipelines across relevant modules.
2. **Stack Trace & Error Log Analysis**:
   - Map exception frames to concrete files and line numbers.
   - Inspect local variable bindings and state transitions leading to the failure.
3. **Git Blame & History Analysis**:
   - Inspect recent git commits, authors, and commit messages on the affected files.
   - Determine when regressions or design shifts were introduced and why.
4. **Test Coverage Mapping**:
   - Locate existing unit, integration, and end-to-end tests covering the target area.
   - Identify gaps in coverage that allowed the bug or performance regression to manifest.

---

### Phase 3: Root-Cause Hypothesis Formulation

Synthesize findings into a concise, technically rigorous, falsifiable hypothesis:

- **Symptom**: The observable, quantified failure (e.g. *"Marbles tunnel through static and dynamic wedges when linear velocity $v > 1200\text{ px/s}$"*).
- **Root Cause**: The exact mechanical or architectural flaw (e.g. *"Discrete Euler integration with fixed timestep $\Delta t = 1/60$. A marble moves 20 px/frame while wedge boundary thickness is 8 px, allowing geometry traversal entirely within a single step without trigger intersection"*).
- **Fix Surface**: Specific candidate modules, algorithms, or components required for remediation (e.g. *"Continuous Collision Detection (CCD) ray-cast sweep or adaptive sub-stepping in `sim/collisions.py`"*).

The hypothesis must be concrete enough that another engineer can confirm or refute it in 30 seconds.

---

### Phase 4: Tree Node Mutation (`workflow_propose_tree_mutation`)

Persist the crystallized pain directly into the project tree using native MCP tools.

1. **Record Pain on Existing Node**:
   Call `workflow_propose_tree_mutation` with `operation: "set_data"`:
   ```json
   {
     "project": "<project>",
     "target_node_id": "<node_id>",
     "operation": "set_data",
     "payload": {
       "pain": "<quantified symptom and technical root cause>",
       "pattern": "<path/glob/to/affected/code/**>"
     },
     "fragment": "fragments/<file>.yaml"
   }
   ```

2. **Architectural Decomposition (Split Pain)**:
   If the investigation reveals that the issue spans multiple distinct subsystems or is too large for a single atomic contract, propose decomposing the concern into child work nodes:
   ```json
   {
     "project": "<project>",
     "target_node_id": "<parent_node_id>",
     "operation": "add_child",
     "payload": {
       "id": "<child_node_id>",
       "title": "<descriptive title>",
       "kind": "work",
       "status": "weak",
       "data": {
         "pain": "<specific child concern>",
         "pattern": "<child_pattern/**>"
       }
     }
   }
   ```

3. **Diff Review Ready**:
   The MCP tool automatically stages changes into `<target>.proposed` without editing tree files directly.

4. **Flag clarify when requirements are still fuzzy** (optional, recommended):
   If GOAL/OUT are not yet decidable, propose `needs_clarify: true`:
   ```json
   {
     "operation": "set_data",
     "payload": {
       "needs_clarify": true
     }
   }
   ```
   User runs `/spec-clarify` before spec-discovery. Clear flag after clarify completes.

---

### Phase 5: Human Gate (Hypothesis Verification)

Present the crystallized hypothesis and proposed scope to the human partner for confirmation:

```text
HYPOTHESIS: <One-sentence technical summary of the root cause>
FIX SURFACE: <Target files and candidate approach>
PROPOSED SCOPE: <Target tree node(s) and pattern>

Confirm root cause hypothesis and scope? Reply: Y/N (or fix: <details>)
```

- If **Y**: Proceed to **`/spec-clarify`** (if `needs_clarify` or fuzzy requirements) or **`/spec-discovery`** / **`/scope-contract`** to stage falsifiable claims.
- If **N / fix**: Incorporate user corrections, adjust exploration, and re-verify.

---

## Anti-Patterns (Strictly Forbidden)

- **Speculative Code Edits**: Never modify implementation code, add print statements, or refactor files during `/understand`.
- **Direct YAML Editing**: Never manually edit `nodes.yaml` or fragment files. All updates must go through `workflow_propose_tree_mutation`.
- **Vague Root Causes**: Statements like *"The error handling could be improved"* or *"The code is messy"* are invalid. State the mechanical root cause.
- **Skipping the Human Gate**: Never jump directly into implementation or contract writing without explicit hypothesis verification from the user.
