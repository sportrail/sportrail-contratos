.PHONY: setup run verify clean

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	@echo "Pronto. Se o weasyprint falhar, instala Pango/Cairo (ver CLAUDE.md)."

# PDF_API_TOKEN protege os três /api/*; sem ele respondem 503. Copia o
# .env.example para .env e preenche-o.
run:
	. .venv/bin/activate && uvicorn app:app --reload --port 8000 $(if $(wildcard .env),--env-file .env,)

verify:
	. .venv/bin/activate && python verify.py

clean:
	rm -rf core/__pycache__ __pycache__
	@echo "Limpo."
