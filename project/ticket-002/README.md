# Ticket 002: Reconcile merged ticket-001 status and intent

- **ID**: ticket-002
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-10-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested inspecting and repairing issues across subactor repositories.
1. Reconcile merged ticket-001 status in `project/ticket-001/README.md` to `DONE`.
2. Fix schema compliance of `project/ticket-001/intent.json` so intent conforms to v3 required fields.
3. Fix marker pair in `project/TICKETS.md` so `readme.sh` can generate ticket indexing.
4. Update `.gitignore` to prevent transient cursor and koru files from making checkouts dirty.

## Acceptance criteria

- [x] AC-01: `project/ticket-001/README.md` is marked `Status: DONE` and `Workflow state: DONE`.
- [x] AC-02: `project/ticket-001/intent.json` conforms to `new-project.intent/v3`.
- [x] AC-03: `project/TICKETS.md` contains the auto-generation markers and valid index table.
- [x] AC-04: Governance check `./project/governance-check.sh` passes cleanly with 0 errors.

## Validation

- Governance: `./project/governance-check.sh` reports `GOV-PASS: passed (0 errors, 0 warnings)`.
- Tests: `pytest` passes cleanly.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
