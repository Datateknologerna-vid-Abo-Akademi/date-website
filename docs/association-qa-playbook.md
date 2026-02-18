# Association QA Playbook

## Purpose
Run repeatable checks across all association configurations (`PROJECT_NAME`) to verify:
- frontend/backend boot with each association
- `meta/site` contract integrity
- default landing route behavior
- module route guarding behavior for enabled/disabled modules

## Command
From repository root:

```bash
python scripts/association_qa.py
```

If you have loaded helpers via `source env.sh dev`, you can also use:

```bash
stack-qa-associations
```

## Output
- Markdown report is written to:
  - `docs/association-qa-report.md`
- Non-zero exit code means at least one hard failure was detected.

## Options
- `--associations date kk biocum on demo`
- `--app-origin http://localhost:8080`
- `--compose-file docker-compose.yml`
- `--timeout-seconds 180`
- `--report-path docs/association-qa-report.md`
- `--keep-running` to keep containers up after checks

## Recommended Usage in Rollout
1. Run before every route-group cutover.
2. Run after backend app/module toggles.
3. Attach generated report to migration sign-off for traceability.
