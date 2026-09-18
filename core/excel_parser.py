"""Lê o Excel de formandos e devolve uma lista de dicionários normalizados.

Dois formatos entram por aqui:

1. **Export do WooCommerce** — o que a loja produz desde 2024, sem qualquer
   edição manual. Cabeçalhos: `First Name (Billing)`, `Last Name (Billing)`,
   `Email (Billing)`, `CC`, `NIF`, `cedula`, `clube`, `Product Name`,
   `Order Total Amount`. O nome vem partido em dois e a ação de formação vem
   por linha (`Product Name`) — é isso que permite o backfill de várias
   formações a partir de um único export.

2. **Folha manual** — `nome`, `email`, `nif`, ... Continua a funcionar: quem
   preparou folhas à mão antes deste módulo não tem de as refazer.

O que este módulo NÃO faz: decidir B2C/B2B. Um `clube` preenchido é um indício,
não uma decisão — se um profissional que indica clube é ou não consumidor é
questão do jurista (ver CLAUDE.md, Guarda-jurídica). A coluna `tipo_contrato`
continua a ser o único override; vazio herda o default do lote.
"""
import datetime
import openpyxl

# Colunas aceites no Excel (cabeçalhos na 1.ª linha, sem distinção de
# maiúsculas). Obrigatório: um nome (inteiro ou partido) e um email.
ALIASES = {
    "nome": ["nome", "nome_completo", "nome completo", "formando"],
    "primeiro_nome": ["first name (billing)", "first name", "primeiro nome",
                      "primeiro_nome"],
    "ultimo_nome": ["last name (billing)", "last name", "ultimo nome",
                    "último nome", "apelido", "ultimo_nome"],
    "nif": ["nif", "contribuinte", "nif/identificacao", "vat", "vat number"],
    "email": ["email", "e-mail", "correio", "email (billing)"],
    # Documento de identificação: é o que a minuta aprovada pede no preâmbulo
    # ("portador do documento de identificação n.º ..."). No WooCommerce é `CC`.
    "doc_identificacao": ["cc", "cartao de cidadao", "cartão de cidadão",
                          "documento", "doc_identificacao", "bi", "cc/bi"],
    "validade_documento": ["validade", "validade_documento", "validade cc",
                           "data de validade"],
    "cedula": ["cedula", "cédula", "cedula de treinador",
               "cédula de treinador", "cedula_treinador"],
    "clube": ["clube", "club", "equipa", "entidade"],
    # Ação de formação por linha — a chave do backfill.
    "curso": ["product name", "curso", "formacao", "formação", "acao",
              "ação", "produto"],
    "valor_pago": ["valor_pago", "valor", "valor pago", "preco", "preço",
                   "order total amount", "total", "order total"],
    "morada": ["morada", "endereco", "endereço", "address (billing)",
               "address 1 (billing)"],
    "concelho": ["concelho", "city (billing)", "cidade", "localidade"],
    "distrito": ["distrito", "state (billing)", "state"],
    "tipo_contrato": ["tipo_contrato", "tipo", "b2b", "b2c", "tipo contrato"],
}

# Campos devolvidos para cada formando. Fixo, para o store e os templates não
# terem de adivinhar o que o Excel trazia.
CAMPOS = ("nome", "nif", "email", "doc_identificacao", "validade_documento",
          "cedula", "clube", "curso", "valor_pago", "morada", "concelho",
          "distrito", "tipo_contrato")


def _mapa_colunas(cabecalhos):
    mapa = {}
    for idx, raw in enumerate(cabecalhos):
        if raw is None:
            continue
        chave = str(raw).strip().lower()
        for campo, nomes in ALIASES.items():
            if chave in nomes:
                mapa.setdefault(campo, idx)
    return mapa


def _formatar_valor(bruto):
    """Normaliza o valor pago para '€ 150,00'.

    O WooCommerce manda o total como número (150, 149.5). O `str()` direto dava
    '€ 150' e '€ 149,5' — um valor monetário num contrato não sai com um
    decimal só.
    """
    if bruto is None or bruto == "":
        return ""
    if isinstance(bruto, (int, float)):
        return f"€ {bruto:,.2f}".replace(",", " ").replace(".", ",")
    texto = str(bruto).strip()
    if not texto:
        return ""
    if texto.startswith("€"):
        return texto
    try:
        numero = float(texto.replace("€", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return texto
    return f"€ {numero:,.2f}".replace(",", " ").replace(".", ",")


def _texto(valor):
    """Célula -> string limpa. Datas saem em dd-mm-aaaa (formato da minuta)."""
    if valor is None:
        return ""
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.strftime("%d-%m-%Y")
    if isinstance(valor, float) and valor.is_integer():
        # NIF/CC lidos como número não podem sair '233385169.0'.
        return str(int(valor))
    return str(valor).strip()


def ler_formandos(caminho_xlsx):
    wb = openpyxl.load_workbook(caminho_xlsx, data_only=True)
    ws = wb.active
    linhas = list(ws.iter_rows(values_only=True))
    if not linhas:
        raise ValueError("O Excel está vazio.")

    mapa = _mapa_colunas(linhas[0])
    tem_nome = "nome" in mapa or "primeiro_nome" in mapa or "ultimo_nome" in mapa
    if not tem_nome or "email" not in mapa:
        raise ValueError(
            "O Excel tem de ter, na primeira linha, uma coluna de email e uma "
            "de nome — 'nome', ou o par 'First Name (Billing)' / "
            "'Last Name (Billing)' do export do WooCommerce.")

    formandos = []
    for linha in linhas[1:]:
        if linha is None or all(c is None for c in linha):
            continue

        def val(campo, default=""):
            i = mapa.get(campo)
            if i is None or i >= len(linha):
                return default
            return _texto(linha[i]) or default

        # Nome inteiro, ou composto do par do WooCommerce.
        nome = val("nome") or " ".join(
            p for p in (val("primeiro_nome"), val("ultimo_nome")) if p).strip()
        if not nome:
            continue

        i_valor = mapa.get("valor_pago")
        valor = _formatar_valor(
            linha[i_valor] if i_valor is not None and i_valor < len(linha) else None)

        # tipo_contrato: normaliza para B2C/B2B; vazio => herda default do lote.
        tipo = val("tipo_contrato").upper().strip()
        tipo = tipo if tipo in ("B2C", "B2B") else ""

        formandos.append({
            "nome": nome,
            "nif": val("nif"),
            "email": val("email"),
            "doc_identificacao": val("doc_identificacao"),
            "validade_documento": val("validade_documento"),
            "cedula": val("cedula"),
            "clube": val("clube"),
            "curso": val("curso"),
            "valor_pago": valor or "—",
            "morada": val("morada"),
            "concelho": val("concelho"),
            "distrito": val("distrito"),
            "tipo_contrato": tipo,
        })

    if not formandos:
        raise ValueError("Não foram encontrados formandos com nome preenchido.")
    return formandos


SEM_CURSO = "(sem ação de formação indicada)"


def agrupar_por_curso(formandos):
    """Agrupa os formandos pela ação de formação lida na linha.

    É isto que transforma um export com o histórico todo em um lote por
    formação. A ordem de saída é a de aparecimento, não alfabética: mantém a
    ordem do export, que é a que o coordenador tem à frente.

    Devolve {nome_da_acao: [formando, ...]}.
    """
    grupos = {}
    for f in formandos:
        grupos.setdefault(f.get("curso") or SEM_CURSO, []).append(f)
    return grupos
