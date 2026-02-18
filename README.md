# Date Website (Decoupled)

Monorepo with:
- `backend/`: Django API, admin, data models, workers
- `frontend/`: Next.js frontend
- `infra/`: proxy and deployment config
- `docs/`: migration and architecture documentation

## Start Full Stack (Docker)
1. Copy env template:
   - `cp .env.example .env`
2. Load helper aliases:
   - `source env.sh dev`
3. Start:
   - `stack-start`
4. Open:
   - `http://localhost:8080`

## Backend-Only Workflow
`backend/env.sh` is still available for backend-only development.

## Key Docs
- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/route-migration-matrix.md`
- `docs/docker-dev-workflow.md`
- `docs/migration-runbook.md`
- `docs/theming-multi-association.md`
