# Scope Contract: Spec discovery triage CLI

## GOAL
User triages AI-proposed claims one at a time and assembles a scope contract without writing prose.

## IN
- claims JSON from AI
- terminal review loop (y/n/s/e/q)
- scope-contract markdown output

## OUT
- web UI triage
- automatic codebase scanning

## MUST
- Approving a claim whose text matches VAGUE_PATTERNS in model.py shows a warning and requires a second y/n

## MUST NOT
- Assemble without GOAL approved or with zero approved claims

## VERIFY
- [ ] `python scripts/spec_discovery.py review <file>` shows one claim at a time with y/n/s/e/q
- [ ] GOAL (and IN/OUT if present) is shown once for y/n approval before any claims
- [ ] Decisions persist in the claims JSON file; `status` shows approved/rejected/skipped/pending counts
- [ ] `assemble` writes `projects/<project>/specs/<node>.md` in scope-contract format from approved claims only

## EXAMPLES
| Case | Input / Situation | Expected |
|------|-------------------|----------|
| vague claim | Handle errors gracefully | warning shown before approve |

## ACCEPTANCE
- [ ] `python scripts/spec_discovery.py review <file>` shows one claim at a time with y/n/s/e/q
- [ ] GOAL (and IN/OUT if present) is shown once for y/n approval before any claims
- [ ] Decisions persist in the claims JSON file; `status` shows approved/rejected/skipped/pending counts
- [ ] `assemble` writes `projects/<project>/specs/<node>.md` in scope-contract format from approved claims only

<!-- spec-discovery: project=ai-workflow node=spec-discovery -->
