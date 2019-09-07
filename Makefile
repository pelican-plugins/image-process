.PHONY: unittest lint deploy ci

unittest:
	pipenv run python -m unittest tests/test_*.py

lint:
	pipenv run pycodestyle .

deploy:
	pipenv run true

ci: lint unittest deploy
