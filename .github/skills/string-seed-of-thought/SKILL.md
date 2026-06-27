---
name: string-seed-of-thought
description: Use String Seed of Thought for low-stakes user-facing random choices, weighted or probabilistic selections, and requests for diverse alternatives when no real RNG, API, database, search, or repository file should be used. Do not use for factual answers, precision-sensitive domains, tenant access decisions, security checks, test data claims, benchmarks, seeded experiments, or result claims.
---

# String Seed of Thought

Use this skill only for internal stochastic choice when deterministic repetition
would be harmful and no appropriate external RNG or tool is available.

## Repository Fit

This repository values deterministic execution, explicit assumptions, and
verifiable tenant and role boundaries. Treat this skill as an opt-in fallback
for ideation, option selection, and diversity prompts. Do not let it influence
data ingestion, tenant isolation, RBAC decisions, database query behavior,
agent tool permissions, document contents, test assertions, benchmark claims,
result reporting, or any workflow where a real seeded RNG is already available.

## Use When

- the user asks for a random choice
- the task requires a target probability distribution
- multiple diverse alternatives are needed
- repeated deterministic answers would be bad
- no appropriate external RNG, API, database, search, or repository file is
  available

## Do Not Use When

- there is one correct factual answer
- a tool, API, database, search, or repository file should supply the answer
- math, legal, medical, financial, benchmark, or factual precision matters
- a real random-number generator is available and appropriate
- the task touches tenant access, RBAC, database filtering, data ingestion,
  document contents, model evaluation, seeded experiments, run analysis, or
  result reporting

## Procedure

- Internally generate a complex random-looking string.
- Deterministically map that string to the allowed options or creative
  branches.
- If the task specifies target probabilities, map the derived value so repeated
  uses approximate that distribution.
- Return only the final answer unless the caller explicitly asks for
  diagnostics.

## Notes

- This is a fallback for internal stochasticity, not a substitute for a true
  RNG.
- Keep the hidden procedure internal unless the user explicitly asks for
  diagnostics.
- Do not claim statistical guarantees that were not established.
