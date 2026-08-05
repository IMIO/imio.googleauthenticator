---
status: testing
phase: 08-coverage-instrument-and-test-layers
source: [08-VERIFICATION.md]
started: 2026-08-05T13:52:59Z
updated: 2026-08-05T13:52:59Z
---

## Current Test

number: 1
name: Push the phase-8 commits and watch the real GitHub Actions run enforce the coverage gate
expected: |
  The `Package Test Workflow` job invokes `bin/test-coverage -t !robot` (wired at
  `.github/workflows/package-test.yml:14`) and reports success at 90% branch coverage.
  A later change that drops coverage below 90%, or breaks a test, produces a red job.
awaiting: user response

## Tests

### 1. Real CI enforcement of the coverage gate

expected: Pushing branch `phase-5` triggers a GitHub Actions run that calls `bin/test-coverage -t !robot` and passes at 90%; a subsequent change below 90% or with a failing test turns the job red.
why_human: All 21 phase-8 commits are local only. `git log origin/phase-5..HEAD` shows the whole range unpushed, and `gh run list` shows no run newer than the pre-phase-8 commit. The `test_command` wiring and the local exit code of `bin/test-coverage` are both verified directly in 08-VERIFICATION.md, but no real CI execution of the coverage-gated command has happened yet. "Enforced in CI" (ROADMAP success criterion 2, requirement QUAL-04) therefore rests on static wiring, not on an observed run.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
