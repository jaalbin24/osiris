ROOT := $(shell git rev-parse --show-toplevel)
VERSION := 0.0.0-test
ROOTFS := /var/lib/machines/osiris-test-noble
MACHINE := osiris-test

.PHONY: help build rootfs test shell destroy clean

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build    Build .deb package into dist/"
	@echo "  rootfs   Bootstrap Ubuntu noble rootfs (one-time)"
	@echo "  test     Build + run nspawn packaging tests"
	@echo "  shell    Build + boot interactive container for debugging"
	@echo "  destroy  Remove rootfs and terminate container"
	@echo "  clean    Destroy + remove build artifacts"

build:
	cd $(ROOT) && poetry build --format wheel
	rm -rf $(ROOT)/staging
	python3 -m venv $(ROOT)/staging/opt/osiris/venv
	$(ROOT)/staging/opt/osiris/venv/bin/pip install --upgrade pip -q
	$(ROOT)/staging/opt/osiris/venv/bin/pip install $(ROOT)/dist/osiris-*.whl -q
	# Fix shebangs: replace build-time staging path with install-time path
	find $(ROOT)/staging/opt/osiris/venv/bin -type f -exec \
		sed -i '1s|#!$(ROOT)/staging/opt/osiris/venv/bin/python|#!/opt/osiris/venv/bin/python|' {} +
	mkdir -p $(ROOT)/dist
	cd $(ROOT) && VERSION=$(VERSION) nfpm package \
		--config packaging/nfpm.yaml \
		--packager deb \
		--target dist/

rootfs:
	sudo bash $(CURDIR)/bootstrap-rootfs.sh $(ROOTFS)

test: build rootfs
	sudo bash $(CURDIR)/run-container.sh $(ROOTFS) $(MACHINE) $(ROOT)/dist $(CURDIR)

shell: build rootfs
	sudo systemd-nspawn --ephemeral \
		--machine=$(MACHINE) \
		--directory=$(ROOTFS) \
		--bind-ro=$(ROOT)/dist:/dist \
		--bind-ro=$(CURDIR):/vagrant

destroy:
	-sudo machinectl terminate $(MACHINE) 2>/dev/null
	-sudo rm -rf $(ROOTFS)

clean: destroy
	rm -rf $(ROOT)/staging $(ROOT)/dist
