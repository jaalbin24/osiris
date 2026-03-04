COMPOSE := docker compose
PROJECT := osiris-integration

.PHONY: help up test down clean logs shell

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  up      Build and start all containers"
	@echo "  test    Run integration tests (starts containers if needed)"
	@echo "  down    Stop containers"
	@echo "  clean   Stop containers and remove volumes"
	@echo "  logs    Tail container logs"
	@echo "  shell   Open a bash shell in the controller container"

up:
	$(COMPOSE) -p $(PROJECT) build
	$(COMPOSE) -p $(PROJECT) up -d --wait

test: up
	$(COMPOSE) -p $(PROJECT) exec -T controller bash /build/tests/integration/run-tests.sh

down:
	$(COMPOSE) -p $(PROJECT) down

clean:
	$(COMPOSE) -p $(PROJECT) down -v --remove-orphans

logs:
	$(COMPOSE) -p $(PROJECT) logs --tail=200

shell:
	$(COMPOSE) -p $(PROJECT) exec controller bash
