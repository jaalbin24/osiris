ROOT := $(shell git rev-parse --show-toplevel)
VERSION := 0.0.0-test

.PHONY: help build test destroy clean

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build    Build .deb package into dist/"
	@echo "  test     Build + run Vagrant packaging tests"
	@echo "  destroy  Destroy Vagrant VM"
	@echo "  clean    Destroy VM and remove build artifacts"

build:
	cd $(ROOT) && poetry build --format wheel
	rm -rf $(ROOT)/staging
	python3 -m venv $(ROOT)/staging/opt/osiris/venv
	$(ROOT)/staging/opt/osiris/venv/bin/pip install --upgrade pip -q
	$(ROOT)/staging/opt/osiris/venv/bin/pip install $(ROOT)/dist/osiris-*.whl -q
	mkdir -p $(ROOT)/dist
	cd $(ROOT) && VERSION=$(VERSION) nfpm package \
		--config packaging/nfpm.yaml \
		--packager deb \
		--target dist/

test: build
	vagrant up --provision
	vagrant ssh -c 'sudo bash /vagrant/run-tests.sh'

destroy:
	vagrant destroy -f

clean: destroy
	rm -rf $(ROOT)/staging $(ROOT)/dist
