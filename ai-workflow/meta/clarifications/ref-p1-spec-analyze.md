# Clarifications: ref-p1-spec-analyze

## Clarifications

### Session 2026-09-14

- Q: When `/implement` is about to start on a node, what must spec-analyze have done? → A: Analyze must be complete or skipped before /implement. Persist run status (and findings). Never edit claims, contract, tree, or constitution. CRITICAL does not hard-block after skip/complete.
- Q: Which artifacts must v1 spec-analyze read when it runs on a node? → A: Claims JSON + assembled scope-contract + clarifications decisions; plus constitution.md when present. Missing constitution is a finding, not an abort. Do not require plan.md or tasks.md.
- Q: If claims JSON or the assembled scope-contract is missing, what must spec-analyze do? → A: Abort: do not mark complete; no findings file. Instruct the user to assemble (or skip).
- Q: Which findings must v1 spec-analyze emit (vs defer to ref-sk-analyze-cross)? → A: Consistency + coverage: claims vs GOAL/IN/OUT/MUST/MUST NOT/VERIFY; clarifications not contradicted; constitution MUST when present; unmapped claims or VERIFY; severities CRITICAL/HIGH/MEDIUM/LOW. Defer Spec Kit duplication/ambiguity/underspec prose-lint to ref-sk-analyze-cross.
- Q: How must agents run v1 spec-analyze, and where must status/findings persist? → A: Skill + MCP tools + CLI (spec-clarify parity). Persist run status and findings JSON under the project dir. Cockpit UI deferred.

## Completion

Status: **complete**

Deferred categories:
- cockpit-ux
- speckit-prose-lint
- plan-tasks-artifacts

Outstanding (low impact):
- findings-path-and-mcp-ids
