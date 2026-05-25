.PHONY: up down logs ps smoke test eval format init-qdrant init-minio phase2a-e2e load-test test-ui build-frontend backup-postgres backup-minio verify-backup

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

ps:
	docker compose ps

smoke:
	docker compose exec app pytest -q apps/edr/tests/smoke

test:
	docker compose exec app pytest -q

eval:
	docker compose exec app python -m apps.edr.evaluation.run --suite goldenset

format:
	docker compose exec app ruff format apps

init-qdrant:
	docker compose exec app python scripts/init_qdrant.py --mapping docs/config/project_source_mapping.json

init-minio:
	docker compose exec app python scripts/init_minio.py

phase2a-e2e:
	docker compose exec app python scripts/phase2a_e2e_validation.py

load-test:
	docker compose exec app python -m apps.edr.evaluation.load_test --requests 10 --concurrency 5

test-ui:
	cd frontend && npm run test:ui

build-frontend:
	cd frontend && npm ci && npm run build

backup-postgres:
	python3 scripts/backup_postgres.py --output-dir backups

backup-minio:
	docker compose exec app python3 scripts/backup_minio.py --output-dir backups

verify-backup:
	@docker compose exec app python3 scripts/verify_backup.py --verify-restored
