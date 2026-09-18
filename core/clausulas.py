"""
Configuração da entidade e texto do contrato de formação.

================================================================================
FONTE DE VERDADE: a minuta "Contrato de Formação Sportrail V1. 2024", aprovada
pela DGERT no pedido de certificação da entidade formadora.

O texto do CORPO do contrato (`MINUTA_APROVADA`) é transcrição literal dessa
minuta. Não se reescreve, não se "melhora" a redação, não se renumera. Se o
documento gerado deixar de coincidir com o que foi aprovado, a certificação
deixa de cobrir o que a Sportrail faz assinar — que é o oposto do objetivo.

Duas anomalias vêm da própria minuta aprovada e estão aqui DE PROPÓSITO:
  1. A Cláusula 3.ª numera os pontos "3." e "4." (devia ser "1." e "2.").
  2. Não existe Cláusula 9.ª — salta da 8.ª para a 10.ª.
Corrigi-las é decisão do jurista sobre um documento aprovado, não de quem
programa. Ver tasks/todo.md (Sessão 8).

A livre resolução (DL 24/2014) NÃO faz parte da minuta aprovada. Por isso vive
em ADENDA, depois das assinaturas do contrato — acrescentar cláusulas ao corpo
alterava o documento aprovado. Qualquer alteração à adenda volta a exigir
revisão jurídica antes de ir para produção.

Nada do que sai impresso pode conter marcadores de andaime: o formando lê e
assina este texto. O verify.py extrai o texto dos PDFs gerados e falha se
encontrar algum — houve marcadores que passaram despercebidos ao grep e só
apareceram no documento final.
================================================================================

As 3 camadas (a leitura continua válida, o conteúdo é que mudou de origem):
  Camada 1 — Identificação/DTP: partes, ação, datas, valor, certificação. Vão no
             preâmbulo e no quadro de destaque do template, não como cláusulas.
  Camada 2 — Lei do consumidor (DL 24/2014): SÓ B2C, e SÓ em adenda.
  Camada 3 — Corpo do contrato: a minuta aprovada, igual em B2C e B2B.
"""

ENTIDADE = {
    # Denominação completa, tal como consta da minuta aprovada.
    "nome": "Sportrail, Sports Training Language, Unipessoal Limitada",
    "nome_curto": "Sportrail, Lda.",
    "nif": "514144785",
    "morada": "Oeiras, Portugal",
    # Quem outorga pela entidade. Na minuta aprovada é a Gerente; é também a
    # Diretora Pedagógica, e é a assinatura que vai pré-aposta no PDF.
    "representante": "Liliana Regina Fernandes",
    "representante_qualidade": "Gerente",
    "diretora": "Liliana Fernandes",   # Diretora/Coordenadora Pedagógica
    # Endereço para onde o formando envia a declaração de livre resolução.
    # Sai impresso na adenda B2C e no anexo do formulário.
    "email": "liliana.fernandes@sportrail.pt",
}

# Identificação da versão da minuta. Sai no rodapé de todas as páginas do corpo,
# tal como no documento aprovado. Mudar isto = mudar o texto aprovado.
VERSAO_MINUTA = "Contrato de Formação Sportrail V1. 2024"

# Prazo legal de livre resolução (DL 24/2014, art. 10.º).
PRAZO_LIVRE_RESOLUCAO_DIAS = 14


# ---------------------------------------------------------------------------
# Camada 3 — corpo do contrato (minuta aprovada pela DGERT)
# ---------------------------------------------------------------------------
# Estrutura de cada cláusula:
#   numero    — o rótulo tal como está na minuta ("CLÁUSULA 10.ª" existe, 9.ª não)
#   titulo    — o subtítulo da cláusula
#   pontos    — lista de blocos. Cada bloco é:
#                 {"n": "1.", "texto": ...}                  ponto numerado
#                 {"texto": ...}                             parágrafo corrido
#                 {"n": "4.", "texto": ..., "alineas": [...]} ponto com alíneas
#               As alíneas são {"l": "a)", "texto": ...}.
#
# Os campos a preencher (nome da ação, modalidade, local, horas, datas) chegam
# do `curso` e são interpolados pelo template — na minuta em papel são os
# tracejados. O que NÃO é campo é texto aprovado e fica literal.

MINUTA_APROVADA = [
    {
        "numero": "CLÁUSULA 1.ª",
        "titulo": "Objeto do Contrato",
        "pontos": [
            {"n": "1.", "texto":
             "O primeira outorgante compromete-se a proporcionar ao segundo "
             "outorgante, a ação de formação profissional de {acao}."},
            {"n": "2.", "texto":
             "Esta ação de formação desenvolve-se na modalidade de {modalidade}, "
             "de acordo com a legislação e demais documentos normativos em vigor."},
            {"n": "3.", "texto":
             "Nos termos do n.º 3 do art.º 4.º do Decreto-Lei n.º 242/88, de 7 de "
             "Julho, o presente contrato não gera nem titula relações de trabalho "
             "subordinado e caduca com a conclusão da acção de formação para que "
             "foi celebrado."},
        ],
    },
    {
        "numero": "CLÁUSULA 2.ª",
        "titulo": "Local, Duração e Horário",
        "pontos": [
            {"n": "1.", "texto":
             "O processo formativo é assegurado pela primeira outorgante "
             "decorrendo a formação nas instalações localizadas em {local}, no "
             "concelho de {concelho_formacao} ou noutras por ele indicadas."},
            {"n": "2.", "texto":
             "A formação tem a duração de {horas} horas, com início em {inicio}, "
             "terminando em {fim} e decorre de acordo com os horários que vierem "
             "a ser fixados pelo primeira outorgante."},
        ],
    },
    {
        "numero": "CLÁUSULA 3.ª",
        "titulo": "Direitos do Formando",
        # A minuta aprovada numera estes pontos "3." e "4.". Ver cabeçalho.
        "pontos": [
            {"n": "3.", "texto":
             "O segundo outorgante terá direito a exigir do primeira outorgante o "
             "cumprimento dos deveres previstos na cláusula 5.ª do presente contrato."},
            {"n": "4.", "texto": "O segundo outorgante tem direito a:", "alineas": [
                {"l": "a)", "texto":
                 "Receber a formação com base nos referenciais de formação, nas "
                 "metodologias e processos de trabalho, aplicados à respetiva saída "
                 "profissional no respeito pelas condições de saúde, higiene e "
                 "segurança no trabalho, exigidos pela legislação em vigor;"},
                {"l": "b)", "texto":
                 "Beneficiar de um seguro contra acidentes ocorridos durante e por "
                 "causa das atividades de formação;"},
                {"l": "c)", "texto":
                 "Obter gratuitamente, no final da ação de formação um Certificado "
                 "de Qualificações e/ou um Diploma e ver registadas na Caderneta "
                 "Individual de Competências as respetivas competências adquiridas "
                 "e certificadas, nos termos da legislação e demais documentos "
                 "normativos aplicáveis;"},
                {"l": "d)", "texto":
                 "Recusar a realização de atividades que não se insiram no objeto "
                 "do curso."},
            ]},
        ],
    },
    {
        "numero": "CLÁUSULA 4.ª",
        "titulo": "Deveres do Formando",
        "pontos": [
            {"n": "1.", "texto": "São deveres do segundo outorgante:", "alineas": [
                {"l": "a)", "texto":
                 "Frequentar com assiduidade e pontualidade a ação de formação, "
                 "visando adquirir os conhecimentos teóricos e práticos que lhe "
                 "forem ministrados, em respeito do Regulamento Interno em vigor;"},
                {"l": "b)", "texto":
                 "Tratar com urbanidade a primeira outorgante, seus representantes, "
                 "trabalhadores e colaboradores;"},
                {"l": "c)", "texto":
                 "Utilizar com cuidado e zelar pela boa conservação dos equipamentos "
                 "e demais bens que lhe sejam confiados para efeitos de formação;"},
                {"l": "d)", "texto":
                 "Suportar os custos de substituição ou reparação dos equipamentos e "
                 "materiais que utilizar no período de formação, fornecidos pela "
                 "primeira outorgante e seus representantes, sempre que os danos "
                 "produzidos resultem de comportamento doloso ou gravemente "
                 "negligente;"},
                {"l": "e)", "texto":
                 "Responder, pela forma e no prazo solicitado, a todos os inquéritos "
                 "formulados pelas primeira outorgante;"},
                {"l": "f)", "texto":
                 "Cumprir os demais deveres emergentes do contrato de formação;"},
                {"l": "g)", "texto":
                 "Conhecer e cumprir as normas e procedimentos instituídos no "
                 "Regulamento da Formação, em vigor à data de início da formação."},
            ]},
        ],
    },
    {
        "numero": "CLÁUSULA 5.ª",
        "titulo": "Deveres da Entidade",
        "pontos": [
            {"texto": "São deveres da primeira outorgante:", "alineas": [
                {"l": "a)", "texto":
                 "Assegurar a formação programada com respeito pela legislação e "
                 "regulamentação em vigor e pelas condições de aprovação da ação de "
                 "formação."},
                {"l": "b)", "texto":
                 "Proceder ao acompanhamento técnico-pedagógico dos formandos durante "
                 "o período em que decorre esta componente de formação;"},
                {"l": "c)", "texto":
                 "Não exigir ao formando tarefas não compreendidas no objeto do curso;"},
                {"l": "d)", "texto": "Cumprir os termos do presente contrato;"},
                {"l": "e)", "texto":
                 "Disponibilizar o Regulamento da Formação em vigor, à data de início "
                 "da formação;"},
                {"l": "f)", "texto":
                 "Passar gratuitamente ao formando, no final da ação, um Certificado "
                 "de Qualificações e/ou Diploma, nos termos da legislação e demais "
                 "documentos normativos aplicáveis."},
            ]},
        ],
    },
    {
        "numero": "CLÁUSULA 6.ª",
        "titulo": "Faltas",
        "pontos": [
            {"texto":
             "Às faltas aplica-se o disposto no Regulamento da Formação em vigor à "
             "data de início da formação."},
        ],
    },
    {
        "numero": "CLÁUSULA 7.ª",
        "titulo": "Alterações Supervenientes",
        "pontos": [
            {"n": "1.", "texto":
             "Quando, por razões alheias à sua vontade e a si não imputáveis, a "
             "primeira outorgante não puder cumprir integralmente o plano de formação "
             "previsto, poderá proceder aos necessários ajustamentos, devendo sempre "
             "comunicar por escrito tal facto ao formando."},
            {"n": "2.", "texto":
             "A alteração do plano de formação pelos motivos referidos no número "
             "anterior não confere ao formando direito a qualquer indemnização."},
        ],
    },
    {
        "numero": "CLÁUSULA 8.ª",
        "titulo": "Cessação do Contrato",
        "pontos": [
            {"n": "1.", "texto":
             "O contrato pode cessar por revogação, por rescisão de uma das partes ou "
             "por caducidade."},
            {"n": "2.", "texto":
             "A rescisão por justa causa, por qualquer das partes, tem que ser "
             "comunicada à outra, por documento escrito ou carta registada, devendo "
             "dela constar o(s) respetivo(s) motivo(s)."},
            {"n": "3.", "texto":
             "O contrato de formação caduca quando se verificar a impossibilidade "
             "superveniente, absoluta e definitiva, do segundo outorgante frequentar a "
             "ação de formação ou de a primeira outorgante lha proporcionar."},
        ],
    },
    {
        # Não há Cláusula 9.ª na minuta aprovada. Ver cabeçalho do módulo.
        "numero": "CLÁUSULA 10.ª",
        "titulo": "Legislação Aplicável",
        "pontos": [
            {"texto":
             "Ao presente contrato, em tudo o que for omisso, aplicar-se-á o disposto "
             "no Decreto-Lei n.º 242/88, de 7 de julho e demais legislação "
             "complementar."},
        ],
    },
]

# Fecho da minuta, antes das assinaturas.
FECHO_MINUTA = ("O presente contrato é feito em duplicado e assinado por ambos os "
                "outorgantes, destinando-se o original, ao primeira outorgante e a "
                "cópia ao segundo outorgante.")


# ---------------------------------------------------------------------------
# Camada 2 — adenda de consumidor (DL 24/2014). SÓ B2C.
# ---------------------------------------------------------------------------
# Fora do corpo aprovado, de propósito: a minuta da DGERT não tem livre
# resolução, e quem compra online enquanto consumidor tem-na por lei. A adenda
# acrescenta o que falta sem tocar no que foi aprovado.

def adenda_livre_resolucao(prazo=PRAZO_LIVRE_RESOLUCAO_DIAS):
    """SÓ B2C. Direito de livre resolução + pedido expresso de início."""
    return [
        ("Cláusula 1.ª — Direito de livre resolução",
         f"Por se tratar de um contrato celebrado à distância, o(a) "
         f"Formando(a), na qualidade de consumidor(a), tem o direito de resolver "
         f"livremente este contrato, sem necessidade de indicar motivo e sem "
         f"qualquer custo, no prazo de {prazo} dias seguidos a contar da data da "
         f"sua celebração, nos termos do Decreto-Lei n.º 24/2014, de 14 de "
         f"fevereiro. Para o efeito, pode usar o formulário de livre resolução "
         f"anexo a este contrato ou qualquer declaração inequívoca dirigida à "
         f"Entidade Formadora (ex.: email para {ENTIDADE['email']}). Cabe ao(à) "
         f"Formando(a) a prova do exercício deste direito dentro do prazo."),
        ("Cláusula 2.ª — Início da formação durante o prazo de resolução",
         "Caso a formação tenha início antes de decorrido o prazo de "
         "livre resolução, o(a) Formando(a) solicita expressamente esse início "
         "antecipado ao aceitar o presente contrato e ao assinalar o consentimento "
         "na submissão. Se vier a exercer o direito de livre resolução depois de a "
         "formação ter começado, fica obrigado(a) a pagar o montante proporcional "
         "ao serviço efetivamente prestado até à data da resolução."),
        ("Cláusula 3.ª — Articulação com o contrato",
         "A presente adenda acrescenta-se ao contrato de formação sem o alterar. "
         "Em tudo o que nela não estiver previsto vigoram as cláusulas do contrato."),
        # OPCIONAL: ao abrigo do art. 17.º do DL 24/2014, o direito de livre
        # resolução pode cessar quando o serviço tenha sido integralmente
        # prestado com consentimento prévio e expresso e reconhecimento da perda
        # do direito. NÃO incluído — acrescentá-lo exige revisão jurídica.
    ]


# ---------------------------------------------------------------------------
# API usada pelo template e pelo verify.py
# ---------------------------------------------------------------------------

def corpo_contrato(curso: dict):
    """Minuta aprovada com os campos do curso já interpolados.

    Os `{campo}` do texto são os tracejados da minuta em papel. Um campo que o
    curso não traga fica como tracejado — o contrato sai para preenchimento
    manual em vez de sair com um dado inventado.
    """
    campos = _campos_do_curso(curso)

    def preencher(texto):
        return texto.format(**campos)

    saida = []
    for cl in MINUTA_APROVADA:
        pontos = []
        for p in cl["pontos"]:
            pontos.append({
                "n": p.get("n", ""),
                "texto": preencher(p["texto"]),
                "alineas": [{"l": a["l"], "texto": a["texto"]}
                            for a in p.get("alineas", [])],
            })
        saida.append({"numero": cl["numero"], "titulo": cl["titulo"],
                      "pontos": pontos})
    return saida


# Tracejado usado quando o dado não existe. Mesmo comprimento do da minuta.
TRACEJADO = "_" * 24


def _campos_do_curso(curso: dict):
    """Mapeia o dicionário `curso` para os campos da minuta."""
    modalidade = (curso.get("modalidade") or "").strip()
    local = (curso.get("local") or "").strip()
    if not local and e_a_distancia(modalidade):
        # A minuta pede um local físico. Numa ação a distância não há, e deixar
        # o tracejado num contrato online era pedir ao formando que inventasse.
        local = "plataforma de formação a distância da entidade formadora"
    return {
        "acao": curso.get("nome") or TRACEJADO,
        "modalidade": modalidade or TRACEJADO,
        "local": local or TRACEJADO,
        "concelho_formacao": (curso.get("concelho") or "").strip() or "Oeiras",
        "horas": _so_numero(curso.get("duracao")) or TRACEJADO,
        "inicio": curso.get("data_inicio") or TRACEJADO,
        "fim": curso.get("data_conclusao") or TRACEJADO,
    }


def _so_numero(duracao):
    """'12 horas' -> '12'. A minuta já escreve "horas" a seguir ao campo."""
    if not duracao:
        return ""
    texto = str(duracao).strip()
    numero = texto.split()[0] if texto.split() else ""
    return numero if numero.replace(",", "").replace(".", "").isdigit() else texto


def e_a_distancia(modalidade: str) -> bool:
    m = (modalidade or "").lower()
    return m.startswith("online") or m.startswith("dist") or "distância" in m


def precisa_formulario_resolucao(tipo: str) -> bool:
    return tipo.upper() == "B2C"


def precisa_adenda(tipo: str) -> bool:
    return tipo.upper() == "B2C"


def texto_consentimento(tipo: str = "B2C") -> str:
    """
    Texto que o formando aceita ao assinar. É a declaração que dá valor
    jurídico à assinatura eletrónica simples (eIDAS) e, em B2C, o pedido
    expresso do art. 4.º do DL 24/2014 para iniciar a formação antes de
    terminado o prazo de livre resolução.

    Vive aqui, com as cláusulas, e não na app que mostra a página: é texto
    legal, tem de ter uma fonte só. Quem desenha a página de assinatura
    pede-o por `/api/contrato-preview`.

    O B2C fala da adenda porque é lá que a livre resolução vive: a minuta
    aprovada pela DGERT não a tem, e acrescentá-la ao articulado alterava o
    documento aprovado.
    """
    if tipo.upper() == "B2C":
        return (
            "Declaro que li e aceito as cláusulas do contrato e da adenda de "
            "livre resolução, e consinto a assinatura eletrónica de ambos, com "
            "o mesmo valor de uma assinatura manuscrita. Solicito expressamente "
            f"o início da formação durante o prazo de livre resolução de "
            f"{PRAZO_LIVRE_RESOLUCAO_DIAS} dias, ficando ciente de que, se vier "
            "a resolver o contrato, pagarei o valor proporcional ao já prestado.")
    return (
        "Declaro que li e aceito as cláusulas do contrato e consinto a "
        "assinatura eletrónica do mesmo, com o mesmo valor de uma assinatura "
        "manuscrita, em representação da entidade adquirente da formação.")
