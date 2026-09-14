# [CHECKLIST TYPE] Checklist: [FEATURE NAME]

**Purpose**: [PURPOSE]
**Created**: [DATE]
**Feature**: [Link to spec.md or relevant documentation]
**Node**: `[NODE_ID]`

**Note**: This checklist is a requirements-quality review artifact ("unit tests for English"). It tests whether the spec/claims are complete, clear, consistent, and measurable — not whether implementation works.
**Review Ownership**: Reviewer-owned. Mark an item `[x]` only when the reviewer determines the requirements-quality criterion is satisfied.
**Marker Semantics**: `[x]` means the criterion has been reviewed and satisfied for requirements quality. It does not mean implementation work is complete.
**Agent rule**: `/implement` and `workflow_checklist_status` are read-only for markers. Agents MUST NOT toggle `[ ]` / `[x]`.

[BODY]

## Notes

- Mark items `[x]` only after review confirms the requirement-quality criterion is satisfied
- Leave items unchecked when they still require clarification, correction, or reviewer evaluation
- `/implement` reads checklist checkbox state as a gate and must not modify markers
- `requirements.md` is the built-in spec-quality checklist; other `*.md` files in this folder are custom (user-only) checklists
- Add comments or findings inline
- Items are numbered sequentially (`CHK001`…) for easy reference
