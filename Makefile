.PHONY: unittest lint build release-test release-public

unittest:
	pipenv run python -m unittest tests/test_*.py

lint:
	pipenv run pycodestyle .

build:
	rm -rf pelican_image_process.egg-info dist/
	pipenv run python setup.py sdist bdist_wheel

release-test:
	pipenv run twine upload --repository-url https://test.pypi.org/legacy/ dist/*

release-public:
	pipenv run twine upload dist/*
