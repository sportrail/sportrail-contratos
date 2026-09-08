"""
Smoke test do pipeline (sem servidor). Corre: `python verify.py` ou `make verify`.

Verifica, ponta-a-ponta e sem rede:
  1. parsing do Excel de exemplo;
  2. geração do PDF B2C (com cláusulas de livre resolução + anexo);
  3. geração do PDF B2B (sem livre resolução);
  4. trilho de auditoria (hash determinístico) presente;
  5. nenhum marcador de andaime no texto extraído dos PDFs.

Sai com código 0 se tudo passar, 1 se algo falhar. Pensado para o Claude Code
poder validar rapidamente que nada partiu.
"""
import sys
import tempfile
from pathlib import Path

from core import excel_parser, contract
from core.clausulas import ENTIDADE, clausulas
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
falhas = []


def check(cond, msg):
    estado = "OK " if cond else "FALHA"
    print(f"[{estado}] {msg}")
    if not cond:
        falhas.append(msg)


def main():
    # 0) Config da entidade que sai impressa no contrato
    check(bool(ENTIDADE.get("email")),
          "ENTIDADE['email'] preenchido (sai na Cláusula 6.ª e no anexo)")

    curso = {"nome": "Goalkeeper Coaching Course",
             "modalidade": "Online (formação a distância)",
             "duracao": "12 horas", "data_inicio": "22/09/2026",
             "data_conclusao": "08/10/2026"}

    # 1) Excel
    formandos = excel_parser.ler_formandos(BASE / "formandos_exemplo.xlsx")
    check(len(formandos) >= 2, f"Excel lido ({len(formandos)} formandos)")

    # 2) Cláusulas por variante
    n_b2c = len(clausulas(online=True, tipo="B2C"))
    n_b2b = len(clausulas(online=True, tipo="B2B"))
    check(n_b2c > n_b2b, f"B2C tem mais cláusulas que B2B ({n_b2c} vs {n_b2b})")

    f = formandos[0]
    sig = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1"
           "HAwCAAAAC0lEQVR42mNk+M8AAAMCAYAAAA0xZ0AAAAASUVORK5CYII=")

    with tempfile.TemporaryDirectory() as tmp:
        # 3) B2C com auditoria
        doc_id = "VERIFY0001"
        aud = contract.construir_auditoria(curso, f, sig, doc_id, "127.0.0.1")
        check(len(aud["hash"]) == 64, "Hash SHA-256 de auditoria gerado")

        p_b2c = Path(tmp) / "b2c.pdf"
        contract.gerar_pdf(contract.render_html(
            curso, f, tipo="B2C", assinatura_formando=sig, auditoria=aud), str(p_b2c))
        n1 = len(PdfReader(str(p_b2c)).pages)
        check(n1 >= 3, f"PDF B2C gerado com anexo de livre resolução ({n1} págs)")

        # 4) B2B
        p_b2b = Path(tmp) / "b2b.pdf"
        contract.gerar_pdf(contract.render_html(
            curso, f, tipo="B2B", assinatura_formando=sig, auditoria=aud), str(p_b2b))
        n2 = len(PdfReader(str(p_b2b)).pages)
        check(n2 < n1, f"PDF B2B sem anexo, menos páginas que B2C ({n2} págs)")

        # 5) Nenhum marcador de andaime pode chegar ao documento do formando.
        # Lemos o texto extraído do PDF, não o código-fonte: dois dos marcadores
        # viviam no template do anexo, que só é renderizado em B2C — um grep aos
        # .py dava tudo limpo enquanto o documento saía sujo.
        for rotulo, caminho in (("B2C", p_b2c), ("B2B", p_b2b)):
            texto = "\n".join(pg.extract_text() or ""
                              for pg in PdfReader(str(caminho)).pages)
            sujos = [m for m in ("JURISTA", "[EMAIL", "RASCUNHO") if m in texto]
            check(not sujos,
                  f"PDF {rotulo} sem marcadores de andaime"
                  + (f" (encontrado: {', '.join(sujos)})" if sujos else ""))

        # O email da entidade tem de sair impresso: é o endereço para onde o
        # formando envia a declaração de livre resolução. Só aparece no B2C.
        texto_b2c = "\n".join(pg.extract_text() or ""
                              for pg in PdfReader(str(p_b2c)).pages)
        check(ENTIDADE["email"] in texto_b2c,
              f"PDF B2C indica o email da entidade ({ENTIDADE['email']})")

    print()
    if falhas:
        print(f"❌ {len(falhas)} verificação(ões) falharam.")
        sys.exit(1)
    print("✅ Tudo OK.")
    sys.exit(0)


if __name__ == "__main__":
    main()
