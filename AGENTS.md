# Repository instructions

These instructions apply to every task performed in this repository.

## Required context before edits

Before modifying application code, tests, database migrations, configuration,
deployment files, CI workflows, or documentation:

1. Read `docs/TRUTH.md` completely.
2. Read every other file in `docs/` completely, including files added there in
   the future.
3. Treat the documented business rules, security requirements, database
   invariants, architecture, and operational constraints as authoritative.
4. Check the requested change against those constraints before editing.

If a required document is missing, unclear, outdated, or conflicts with the
requested change, stop and explain the conflict before making edits. Do not
silently weaken or remove a documented constraint.

## Keep documentation synchronized

After making a change, review every file in `docs/` for impact and update all
affected documentation in the same change. In particular:

- Keep `docs/TRUTH.md` aligned with current business rules, security guarantees,
  database invariants, and externally observable behavior.
- Keep `docs/STRUCTURE.md` aligned with the current architecture and repository
  layout.
- Keep `docs/README.md` aligned with setup, operation, testing, and API behavior.
- Record relevant changes in `docs/CHANGELOG.md` using its existing format.

Do not update documentation merely to create churn. If a document is unaffected,
leave it unchanged. Before finishing, state which documentation files were
updated or confirm that the review found no documentation changes necessary.

