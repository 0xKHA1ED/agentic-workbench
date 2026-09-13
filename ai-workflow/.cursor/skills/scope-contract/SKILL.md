---
name: scope-contract
description: Turn messy intent into a skimmable scope contract (GOAL/IN/OUT/MUST/VERIFY with executable assertions + examples + checklist). Use when user invokes /scope-contract, asks for a fast spec, scope contract, or falsifiable spec before implementation. Manual-only — never auto-invoke.
disable-model-invocation: true
---

# Scope Contract

Produce specs that take **under 60 seconds to review**. No prose essays. No design docs. No implementation steps.

Announce: "Using scope-contract skill."

## Modes

Detect from user message:
- **CREATE** (default): user gives intent → output contract
- **REVIEW**: user gives existing spec/contract → output review block only

---

## CREATE mode

### Step 1 — Clarify (max 2 questions)

Ask **only** if GOAL or MUST NOT cannot be inferred. One question at a time. If intent is clear, skip to Step 2.

### Step 2 — Output exactly this structure

No extra sections. No paragraphs outside the template.

```markdown
# Scope Contract: <short title>

## GOAL
<one sentence — observable outcome>

## IN
- <what's in scope — bullets only>

## OUT
- <explicit exclusions — bullets only>

## MUST
- <invariants — max 5 bullets>

## MUST NOT
- <red lines — max 5 bullets>

## VERIFY
- [ ] check_type: pytest | `pytest <path/to/test.py> -k <test_name>`
- [ ] check_type: command | `python3 <command_and_args>`
- [ ] check_type: ast_symbol | `<path/to/file.py>` exports `[SymbolA, SymbolB]`
- [ ] <observable pass/fail check if not purely automated>

## EXAMPLES
| Case | Input / Situation | Expected |
|------|-------------------|----------|
| <happy path> | | |
| <edge case> | | |

## ACCEPTANCE
- [ ] <checkbox — same as VERIFY but user-facing>
```

### Rules

- **GOAL**: one sentence. No "why" or background.
- **IN / OUT**: nouns and boundaries, not implementation.
- **MUST / MUST NOT**: falsifiable. "Handle errors gracefully" is banned — say what happens on error.
- **VERIFY**: every item must be checkable without reading code. Support executable assertion syntax:
  - `check_type: pytest | <command>` — specific test command executing via pytest
  - `check_type: command | <command>` — shell/python command expecting exit code 0
  - `check_type: ast_symbol | <file> exports [<symbols>]` — verifiable AST symbol definitions
  - Executable verification powers automated test execution via `workflow_execute_verification`.
- **EXAMPLES**: 2–4 rows max. Capture the tricky cases.
- **ACCEPTANCE**: mirror VERIFY in plain language for non-engineers when relevant.
- Total output **under 40 lines** excluding the examples table.
- Do **not** write files, save specs, or start implementation unless user says "save" or "implement".

### Step 3 — Vision check (one line)

End with:

```
VISION CHECK: <one sentence — what you're verifying the user wanted>
Reply: approve | fix: <what to change>
```

---

## REVIEW mode

User pastes or @-references a spec. Output **only**:

```markdown
## Spec Review

**STATUS:** APPROVED | FIX

**Issues** (only if FIX — max 3, each one line):
- ...

**30s scan:** GOAL ✓/✗ | OUT explicit ✓/✗ | VERIFY executable / falsifiable ✓/✗ | EXAMPLES cover risk ✓/✗
```

**Approve** unless: ambiguous GOAL, missing OUT, VERIFY not falsifiable or missing executable assertions, or no example for the riskiest case.

Do not rewrite the spec unless user says "fix it".

---

## Anti-patterns (never output)

- Rationale / background / "approach" sections
- Implementation steps or file paths (unless user explicitly asks for IN to list modules)
- "Should be performant / scalable / robust" without a number or test
- Duplicate info across sections
- More than 5 MUST or MUST NOT items
