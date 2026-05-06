.PHONY: up down logs ps smoke test eval format init-qdrant

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
	docker compose exec app python scripts/init_qdrant.py --mapping docs/config/project_source_mapping.example.json
