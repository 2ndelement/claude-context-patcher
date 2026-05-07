.PHONY: install patch check restore clean help

help:
	@echo "Claude Context Patcher"
	@echo ""
	@echo "Usage:"
	@echo "  make patch      - Search and patch Claude Code"
	@echo "  make check      - Check current patch status"
	@echo "  make restore    - Restore from backup"
	@echo "  make clean      - Remove backup files"
	@echo "  make help       - Show this help message"

patch:
	python3 -m src.main --auto

check:
	python3 -m src.main --check

restore:
	python3 -m src.main --restore

clean:
	rm -f *.bak
	find . -name "*.bak" -delete 2>/dev/null || true

install:
	pip install -e .
