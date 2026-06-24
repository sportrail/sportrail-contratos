"""
Configuração da entidade e cláusulas do contrato, organizadas em 3 camadas.

================================================================================
AVISO: TODO o texto legal abaixo é um RASCUNHO de andaime. NÃO é aconselhamento
jurídico. Os trechos marcados com [JURISTA] têm de ser confirmados/reescritos
pelo advogado da Sportrail antes de qualquer uso real — em especial a Camada 2
(direito de livre resolução, DL 24/2014) e a renúncia do art. 17.º.
================================================================================

As 3 camadas:
  Camada 1 — Identificação/DTP: dados que tornam o contrato auditável pela DGERT
             (partes, ação, datas, valor, certificação). Vão no quadro de
             destaque do template, não como cláusulas — logo não estão aqui.
  Camada 2 — Lei do consumidor (DL 24/2014): SÓ no contrato B2C. Direito de
             livre resolução de 14 dias + pedido expresso para início antecipado.
  Camada 3 — Contrato geral: objeto, frequência, pagamento, certificação, RGPD,
             desistência, disposições finais. Comum a B2C e B2B.
"""

ENTIDADE = {
    "nome": "Sportrail, Lda.",
    "nif": "514144785",
    "morada": "Oeiras, Portugal",
    "diretora": "Liliana Fernandes",   # Diretora/Coordenadora Pedagógica
}

# Prazo legal de livre resolução (DL 24/2014, art. 10.º).
PRAZO_LIVRE_RESOLUCAO_DIAS = 14


def _camada3_inicio():
    return [
        ("Cláusula 1.ª — Objeto",
         "O presente contrato tem por objeto a frequência, pelo(a) Formando(a), "
         "da ação de formação identificada no quadro acima, ministrada pela "
         "Entidade Formadora."),
        ("Cláusula 2.ª — Duração e calendário",
         "A formação decorre entre as datas de início e de conclusão indicadas, "
         "com a duração total especificada, segundo o cronograma disponibilizado "
         "ao(à) Formando(a)."),
        ("Cláusula 3.ª — Condições de frequência",
         "O(A) Formando(a) compromete-se a frequentar a formação com assiduidade "
         "e a cumprir as normas de funcionamento e o regulamento da Entidade "
         "Formadora."),
        ("Cláusula 4.ª — Pagamento",
         "O valor da formação é o indicado no quadro acima, considerando-se "
         "integralmente liquidado na data de celebração do presente contrato."),
        ("Cláusula 5.ª — Certificação",
         "A conclusão com aproveitamento confere direito a certificado de formação "
         "profissional, emitido nos termos da legislação aplicável, "
         "designadamente através da plataforma SIGO."),
    ]


def _camada2_livre_resolucao(prazo=PRAZO_LIVRE_RESOLUCAO_DIAS):
    """SÓ B2C. Direito de livre resolução + pedido expresso de início. [JURISTA]"""
    return [
        ("Cláusula 6.ª — Direito de livre resolução",
         f"[JURISTA] Por se tratar de um contrato celebrado à distância, o(a) "
         f"Formando(a), na qualidade de consumidor(a), tem o direito de resolver "
         f"livremente este contrato, sem necessidade de indicar motivo e sem "
         f"qualquer custo, no prazo de {prazo} dias seguidos a contar da data da "
         f"sua celebração, nos termos do Decreto-Lei n.º 24/2014, de 14 de "
         f"fevereiro. Para o efeito, pode usar o formulário de livre resolução "
         f"anexo a este contrato ou qualquer declaração inequívoca dirigida à "
         f"Entidade Formadora (ex.: email para [EMAIL]). Cabe ao(à) Formando(a) a "
         f"prova do exercício deste direito dentro do prazo."),
        ("Cláusula 7.ª — Início da formação durante o prazo de resolução",
         "[JURISTA] Caso a formação tenha início antes de decorrido o prazo de "
         "livre resolução, o(a) Formando(a) solicita expressamente esse início "
         "antecipado ao aceitar o presente contrato e ao assinalar o consentimento "
         "na submissão. Se vier a exercer o direito de livre resolução depois de a "
         "formação ter começado, fica obrigado(a) a pagar o montante proporcional "
         "ao serviço efetivamente prestado até à data da resolução."),
        # OPCIONAL [JURISTA]: ao abrigo do art. 17.º do DL 24/2014, o direito de
        # livre resolução pode cessar quando o serviço tenha sido integralmente
        # prestado com consentimento prévio e expresso e reconhecimento da perda
        # do direito. NÃO incluído por defeito por exigir validação jurídica.
    ]


def _camada3_fim(online=True):
    base = [
        ("Cláusula — Proteção de dados",
         "Os dados pessoais do(a) Formando(a) são tratados pela Entidade Formadora "
         "exclusivamente para fins de gestão da formação e certificação, nos termos "
         "do RGPD, sendo conservados pelos prazos legalmente exigidos."),
        ("Cláusula — Desistência e cancelamento",
         "[JURISTA] Sem prejuízo do direito de livre resolução quando aplicável, as "
         "condições de desistência, cancelamento e eventual reembolso constam do "
         "regulamento da Entidade Formadora, que o(a) Formando(a) declara conhecer "
         "e aceitar."),
        ("Cláusula — Disposições finais",
         "Os casos omissos regem-se pela legislação aplicável, designadamente a "
         "Portaria n.º 851/2010, de 6 de setembro. O presente contrato é assinado "
         "por ambas as partes, produzindo efeitos a partir da data da assinatura "
         "do(a) Formando(a)."),
    ]
    if not online:
        base.insert(0, (
            "Cláusula — Seguro",
            "Durante a frequência da formação presencial, o(a) Formando(a) "
            "encontra-se abrangido(a) por seguro de acidentes pessoais."))
    return base


def clausulas(online: bool = True, tipo: str = "B2C"):
    """
    Devolve a lista de cláusulas para a variante pedida.
      tipo="B2C" -> inclui Camada 2 (livre resolução).
      tipo="B2B" -> sem Camada 2 (empresa/clube não é consumidor).
    """
    blocos = _camada3_inicio()
    if tipo.upper() == "B2C":
        blocos = blocos + _camada2_livre_resolucao()
    blocos = blocos + _camada3_fim(online=online)

    # Renumeração sequencial limpa das cláusulas (1.ª, 2.ª, ...).
    out = []
    for i, (titulo, texto) in enumerate(blocos, start=1):
        # mantém o sufixo descritivo depois do travessão, renumerando o prefixo
        if "—" in titulo:
            _, desc = titulo.split("—", 1)
            titulo = f"Cláusula {i}.ª —{desc}"
        out.append({"titulo": titulo, "texto": texto})
    return out


def precisa_formulario_resolucao(tipo: str) -> bool:
    return tipo.upper() == "B2C"
