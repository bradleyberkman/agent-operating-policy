# AI code review standard

## Purpose

AI code review finds consequential defects before a change is accepted. It supplements tests, static analysis, and human product judgment. It should improve the code without obstructing reasonable progress or demanding perfection.

## Review target

Review the exact requested diff against:

- its stated intent and acceptance conditions;
- the current base revision;
- applicable repository rules;
- directly affected behavior and interfaces.

Identify the base and head revisions when available. If the target or intent cannot be established, report the review as incomplete rather than clean.

A review applies only to the artifact inspected. A changed head or base requires a new review.

## Standard review

Inspect the changed code, relevant tests, and directly affected callers and dependencies. Look for:

- incorrect behavior and regressions;
- broken edge cases or error handling;
- incompatible interface or data-contract changes;
- security, privacy, or authorization failures;
- unnecessary complexity that creates a concrete maintenance or correctness risk;
- tests that pass without exercising the behavior they claim to protect.

Use available code, tests, and documentation to verify suspected problems. Do not infer behavior from names alone.

Leave formatting, linting, type checking, spelling, and other deterministic checks to automated tooling.

## Elevated review

Use elevated review when a change affects:

- authentication, authorization, sessions, secrets, or cryptography;
- personal, customer, financial, or production data;
- billing or other monetary effects;
- migrations, destructive writes, or irreversible external actions;
- concurrency, shared state, or retry and idempotency behavior;
- deployment, security, permission, or policy controls;
- public interfaces or widely shared infrastructure.

Elevated review examines the surrounding trust boundaries, data flow, compatibility, rollback, and failure recovery. It expands the inspection area without lowering the evidence required for a finding.

## Finding standard

Report a finding only when all of the following are present:

1. A specific affected location.
2. A plausible execution path or triggering condition.
3. A concrete incorrect outcome.
4. Evidence from the code, contract, test behavior, or authoritative documentation.
5. A reasonable correction or safe direction.

Investigate uncertain candidates when possible. Otherwise omit them or state that the review is incomplete. Do not manufacture findings to justify the review.

Do not report:

- personal style or naming preferences;
- optional refactors or speculative future improvements;
- issues already reported by deterministic checks;
- missing comments, documentation, or tests without a concrete resulting risk;
- pre-existing problems the change does not introduce or materially worsen.

A clean review is a valid and useful result.

## Severity

Classify findings by impact:

- `critical`: A credible path to unauthorized access, sensitive-data exposure, corruption or loss of important data, irreversible harmful effects, or widespread failure. The change must not proceed.
- `important`: A concrete correctness, regression, compatibility, or reliability defect in a supported path. Fix it before considering the change complete.
- `advisory`: A non-blocking improvement. Do not emit advisories during standard automated review unless explicitly requested.

Higher model effort may inspect more code. It must not lower these severity or evidence standards.

## Output

Start with one verdict:

- `clean`
- `findings`
- `incomplete`

For each finding, provide:

- severity and a concise title;
- file and line;
- triggering scenario;
- resulting behavior and impact;
- supporting evidence;
- the smallest safe correction direction.

Combine findings with the same root cause. Do not repeat the same issue at every affected line.

For an incomplete review, name the missing evidence and the exact action needed to complete it.

## Review boundary

The review judgment is read-only. It may publish findings and a review receipt, but it does not edit candidate code or treat a delivery action as evidence that review occurred. Any handoff, approval request, merge, deployment, or ticket transition that follows a clean review is governed by a separate repository contract.

## Receipt

Record when the runner provides the information:

- repository, base revision, and head revision;
- trigger and review profile;
- reviewer identity, provider, model, and effort;
- immutable review-event identity when one exists;
- checks inspected or executed;
- verdict, findings, and unresolved count;
- elapsed time and cost.

Use accepted and dismissed findings to recalibrate the policy. Narrow or remove rules that repeatedly create noise.

## Calibration for a one-person system

- Review for the system's actual users, callers, and scale. The system has one primary maintainer. Do not require speculative enterprise architecture, generalized abstractions, high-availability machinery, or organizational process. Do flag complexity that makes the system harder for one person to understand, operate, or repair.
- Flag any change that unnecessarily broadens external effects, production or customer-data access, credential scope, identity authority, destructive capability, or spend. Pay particular attention to unattended automation, which must remain scoped, bounded, and unable to authorize its own expansion.
- Respect the declared source of truth. Flag hand-edited generated output, duplicated canonical facts, copied live identifiers, or changes made in a rendering instead of its owning source. Live schemas and generated bindings outrank remembered or copied field names and identifiers.

## Reference basis

- [OpenAI Codex code review guidance](https://developers.openai.com/codex/integrations/github)
- [Anthropic Claude Code Review](https://docs.anthropic.com/en/docs/claude-code/code-review)
- [Google Engineering Practices: Code Review](https://google.github.io/eng-practices/review/reviewer/)
- [OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html)
