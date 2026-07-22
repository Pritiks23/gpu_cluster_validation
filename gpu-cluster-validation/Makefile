.PHONY: help install test test-cov lint format clean docker-build docker-run validate

# Variables
PYTHON := python3.10
DOCKER_IMAGE := gpu-cluster-validation:latest
DOCKER_REGISTRY := your-registry.com/gpu-cluster-validation
CONFIG_FILE := config/cluster.yaml

help:
	@echo "GPU Cluster Validation Suite - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make lint             Run linters (ruff, mypy)"
	@echo "  make format           Format code with black"
	@echo "  make test             Run test suite"
	@echo "  make test-cov         Run tests with coverage report"
	@echo ""
	@echo "Deployment:"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-push      Push image to registry"
	@echo ""
	@echo "Validation:"
	@echo "  make validate         Run validation on configured cluster"
	@echo "  make validate-docker  Run validation in Docker"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove build artifacts and cache"

install:
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/ --ignore-missing-imports

format:
	$(PYTHON) -m black src/ tests/
	$(PYTHON) -m ruff check src/ tests/ --fix

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	rm -rf build dist *.egg-info

docker-build:
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE) .

docker-push: docker-build
	docker tag $(DOCKER_IMAGE) $(DOCKER_REGISTRY)
	docker push $(DOCKER_REGISTRY)

validate:
	gpu-cluster-validate --cluster $(CONFIG_FILE) --output reports/

validate-docker:
	docker-compose -f docker/docker-compose.yml run validator \
		--cluster /app/config/cluster.example.yaml \
		--output /app/reports/

validate-debug:
	gpu-cluster-validate --cluster $(CONFIG_FILE) --output reports/ --log-level DEBUG

.DEFAULT_GOAL := help
