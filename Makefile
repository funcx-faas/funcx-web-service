.PHONY: lint
lint:
	tox -e lint

.PHONY: test
test:
	tox

.PHONY: py-safety
py-safety:
	tox -e safety
