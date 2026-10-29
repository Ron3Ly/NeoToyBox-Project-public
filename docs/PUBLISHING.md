# Publishing and CI policy

Publish this directory as a fresh independent repository. Do not copy .git or branches/tags/history from a private deployment repository. Do not change an existing private repository's visibility to publish these examples.

1. Review every allowed file and its SHA-256 in .public-manifest.json.
2. Run tools/ci_check.py locally with requirements-ci.txt.
3. Use a feature branch; commit/push/create a PR only after local tests pass.
4. Require the GitHub Actions merge-gate check on main, an up-to-date branch, PR-only changes, no bypass and no force pushes/deletion.
5. Enable auto-merge only on the approved automation PR. External contributor PRs require maintainer review.
6. Accept only explicit success. Missing, skipped, cancelled, failed or conflicting changes must not merge.

On legitimate source changes, review the diff and update the exact hash manifest in the same PR. Do not regenerate it to hide a failed privacy check. Review workflows and dependency changes as executable code.

The selected-actions policy permits only the pinned checkout and setup-python commits listed in the workflow. Workflow permissions stay contents: read; a separate authenticated GitHub integration may create the branch/PR and request native auto-merge. The integration is not given a ruleset bypass.

Public Actions logs are public data. Require approval for all external contributors and never attach private-network runners or credentials to this repository.
