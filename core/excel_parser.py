"""Lê o Excel de formandos e devolve uma lista de dicionários normalizados."""
import openpyxl

# Colunas aceites no Excel (cabeçalhos na 1.ª linha, sem distinção de maiúsculas).
# Apenas 'nome' e 'email' são obrigatórios; o resto é opcional.
ALIASES = {
    "nome": ["nome", "nome_completo", "nome completo", "formando"],
    "nif": ["nif", "contribuinte", "nif/identificacao"],
    "email": ["email", "e-mail", "correio"],
    "valor_pago": ["valor_pago", "valor", "valor pago", "preco", "preço"],
    "morada": ["morada", "endereco", "endereço"],
    "tipo_contrato": ["tipo_contrato", "tipo", "b2b", "b2c", "tipo contrato"],
}


def _mapa_colunas(cabecalhos):
    mapa = {}
    for idx, raw in enumerate(cabecalhos):
        if raw is None:
            continue
        chave = str(raw).strip().lower()
        for campo, nomes in ALIASES.items():
            if chave in nomes:
                mapa[campo] = idx
    return mapa


def ler_formandos(caminho_xlsx):
    wb = openpyxl.load_workbook(caminho_xlsx, data_only=True)
    ws = wb.active
    linhas = list(ws.iter_rows(values_only=True))
    if not linhas:
        raise ValueError("O Excel está vazio.")

    mapa = _mapa_colunas(linhas[0])
    if "nome" not in mapa or "email" not in mapa:
        raise ValueError(
            "O Excel tem de ter pelo menos as colunas 'nome' e 'email' "
            "na primeira linha.")

    formandos = []
    for linha in linhas[1:]:
        if linha is None or all(c is None for c in linha):
            continue
        nome = linha[mapa["nome"]]
        if not nome:
            continue

        def val(campo, default=""):
            i = mapa.get(campo)
            if i is None or i >= len(linha) or linha[i] is None:
                return default
            return str(linha[i]).strip()

        valor = val("valor_pago")
        # Normaliza valor para "€ 49,00" se vier número.
        if valor and not valor.startswith("€"):
            valor_fmt = valor.replace(".", ",")
            valor = f"€ {valor_fmt}"

        # tipo_contrato: normaliza para B2C/B2B; vazio => herda default do lote.
        tipo = val("tipo_contrato").upper().strip()
        tipo = tipo if tipo in ("B2C", "B2B") else ""

        formandos.append({
            "nome": str(nome).strip(),
            "nif": val("nif"),
            "email": val("email"),
            "valor_pago": valor or "—",
            "morada": val("morada"),
            "tipo_contrato": tipo,
        })

    if not formandos:
        raise ValueError("Não foram encontrados formandos com nome preenchido.")
    return formandos
