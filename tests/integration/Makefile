COMPOSE := docker compose
PROJECT := osiris-integration

.PHONY: up test down clean logs shell

up:
	$(COMPOSE) -p $(PROJECT) build
	$(COMPOSE) -p $(PROJECT) up -d --wait

test: up
	$(COMPOSE) -p $(PROJECT) exec -T controller bash /app/tests/integration/run-tests.sh

down:
	$(COMPOSE) -p $(PROJECT) down

clean:
	$(COMPOSE) -p $(PROJECT) down -v --remove-orphans

logs:
	$(COMPOSE) -p $(PROJECT) logs -f

shell:
	$(COMPOSE) -p $(PROJECT) exec controller bash
