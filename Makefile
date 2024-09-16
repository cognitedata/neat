.PHONY: run-explorer run-tests run-linters build-ui build-python build-docker run-docker compose-up
version="0.92.2"
run-explorer:
	@echo "Running explorer API server..."
	# open "http://localhost:8000/static/index.html" || true
	mkdir -p ./data
	export NEAT_CONFIG_PATH=./data/config.yaml && \
	poetry run uvicorn --host 0.0.0.0 cognite.neat.app.api.explorer:app

run-tests:
	@echo "Running tests..."
	poetry run pytest

run-regen-test:
	@echo "Regenerating test data for failed test. This will overwrite the existing test data !!!!!! Use with caution !!!!!!"
	poetry run pytest --force-regen

configure:
	@echo "Configuring..."
	poetry install --extras all
	cd cognite/neat/app/ui/neat-app; npm install

run-linters:
	poetry run pre-commit run --all-files

run-all-checks : run-linters run-tests

build-ui:
	@echo "Building react UI app"
	cd cognite/neat/app/ui/neat-app; npm run build

build-python: build-ui
	@echo "Building Python wheels"
	poetry build --format wheel

start-ui-dev:
	@echo "Starting NodeJs UI dev server"
	cd cognite/neat/app/ui/neat-app; npm start

poetry-export:
	@echo "Exporting poetry dependencies"
	poetry export -f requirements.txt --output requirements.txt --extras "graphql" --extras "service"

build-docker: poetry-export
	@echo "Building docker image"
	mkdir -p data
	docker build -t cognite/neat:${version} -t cognite/neat:latest .
	rm requirements.txt

run-docker:
	@echo "Running docker image with mounted data folder"
	docker run --rm -p 8001:8000 --name neat -v $(shell pwd)/docker/vol_data:/app/data  cognite/neat:latest

run-clean-docker:
	@echo "Running docker image with temp data folder"
	docker run --rm -p 8001:8000 --name neat cognite/neat:latest

test-docker: build-docker run-clean-docker
	@echo "Building new docker image and running neat from latest image"

defaults-cleanup:
	@echo "Running defaults cleanup"
	rm -r ./docker/vol_data/*
	rm -r ./docker/vol_shared/*

compose-up:
	@echo "Running docker-compose"
	cd ./docker ; mkdir -p vol_data vol_shared ; docker compose up

compose-up-d:
	@echo "Running docker-compose detached"
	cd ./docker ; mkdir -p vol_data vol_shared ; docker compose up --detach

compose-neat-up:
	@echo "Running docker-compose for neat only"
	cd ./docker ; mkdir -p vol_data vol_shared ; docker compose up neat

run-docs:
	@echo "Running mkdocs"
	mkdocs serve --dev-addr 127.0.0.1:8010

gen-steps-md:
	@echo "Generating step docs"
	poetry run python scripts/generate_steps_md.py

run-toolkit:
	@echo "Setup access for test runner"
	poetry run cdf-tk build scripts/integration_runner/ --env dev
	poetry run cdf-tk deploy
