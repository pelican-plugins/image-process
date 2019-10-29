.PHONY: unittest lint build \
	prep-release release-test release-public

unittest:
	pipenv run python -m unittest tests/test_*.py

lint:
	pipenv run pycodestyle .

build:
	rm -rf pelican_image_process.egg-info dist/
	pipenv run python setup.py sdist bdist_wheel

prep-release: lint build unittest

release-test: prep-release
	pipenv run twine upload --repository-url https://test.pypi.org/legacy/ dist/*

release-public: prep-release
	pipenv run twine upload dist/*
