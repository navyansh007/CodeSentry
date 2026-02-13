# Makefile for CodeSentry

.PHONY: install setup clean test run help

# Default target
help:
	@echo "CodeSentry - AI-Powered Code Review System"
	@echo ""
	@echo "Available commands:"
	@echo "  make install     - Install CodeSentry and dependencies"
	@echo "  make setup       - Set up virtual environment and install"
	@echo "  make clean       - Clean up build artifacts and cache"
	@echo "  make run         - Run CodeSentry on current directory"
	@echo "  make test        - Run a test review on the CodeSentry itself"
	@echo "  make help        - Show this help message"

# Install dependencies and CodeSentry
install:
	pip install -r requirements.txt
	pip install -e .
	@echo ""
	@echo "✓ Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Set HF_TOKEN: export HF_TOKEN='your_token'"
	@echo "  2. Run: codesentry --help"

# Set up virtual environment and install
setup:
	python -m venv venv
	@echo ""
	@echo "✓ Virtual environment created!"
	@echo ""
	@echo "Activate it with:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"
	@echo ""
	@echo "Then run: make install"

# Clean up build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .chroma_db/
	rm -rf reports/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	@echo "✓ Cleanup complete!"

# Run CodeSentry on current directory
run:
	codesentry --clear-cache

# Test CodeSentry by reviewing itself
test:
	@echo "Running CodeSentry on itself..."
	codesentry --path . --output ./test-reports
	@echo ""
	@echo "✓ Test complete! Check test-reports/ for results"
