.PHONY: lint
lint:
	tox -e lint

.PHONY: test
test:
	tox

.PHONY: py-safety
py-safety:
	tox -e safety

# use sed to trim leading whitespace, and `sort -u` to remove duplicates
# intermediate file allows the use of tee, to show output, and saves the frozen
# deps
#
# the funcx git requirements are intentionally excluded from the deptree
# because they look to pip like a conflict once frozen
# they are pulled out of the `requirements.in` data to get a complete
# requirement specification
#
# FIXME:
# the funcx requirement munging should be possible to remove as soon as
# we've removed the dependency on the forwarder and switch to a packaged version
# of the SDK
.PHONY: freezedeps
freezedeps:
	echo "# frozen requirements; generate with 'make freezedeps'" > requirements.txt
	tox -qq -e freezedeps | tee frozen-requirements-tree.txt
	sed 's/ //g' frozen-requirements-tree.txt | sort -u >> requirements.txt
	cat requirements.in | grep -E '^git' | grep 'funcx-faas' >> requirements.txt
