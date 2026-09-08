.PHONY: setup run verify clean

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	@echo "Pronto. Se o weasyprint falhar, instala Pango/Cairo (ver CLAUDE.md)."

# Carrega o .env se existir (ADMIN_USER/ADMIN_PASS; sem eles a zona de
# coordenação responde 503). Copia-o de .env.example.
run:
	. .venv/bin/activate && uvicorn app:app --reload --port 8000 $(if $(wildcard .env),--env-file .env,)

verify:
	. .venv/bin/activate && python verify.py

clean:
	rm -f data/state.json data/pdfs/*.pdf data/arquivo/*.pdf data/upload_*.xlsx
	rm -rf core/__pycache__
	@echo "Limpo."
