# Contributing

Keep it simple.

- Branch from `main`. Production is tracked by promoted image tags, not a long-lived branch.
- Open a pull request into `main`.
- Have the pull request reviewed and accepted by someone else before it is merged.
- Run the relevant tests and checks for your change.
- Update docs or config examples if your change affects them.
- **Squash merge into `main`**. A feature, fix, docs change, or cleanup branch should normally land as one commit on `main`.
- Give the pull request title a conventional-commit prefix (`feat:`, `fix:`, `docs:`, `ci:`, `build(deps):`, ...). Release notes are grouped from these prefixes, so the prefix decides which section the change appears under. Add the `ignore-for-release` label if a PR should stay out of the release notes.

By contributing, you agree that your software source code contributions are
licensed under this repository's AGPL-3.0-or-later software license. Non-code
materials are handled according to [LICENSE-NOTICE.md](LICENSE-NOTICE.md).

That last point is the important one: branch history can be messy, but the history on `main` should stay clean and readable.

For local setup and project workflow, see `README.md`.
