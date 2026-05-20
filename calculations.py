"""DRE calculation engine — Simples Nacional and Lucro Real."""

from models import SimplesNacionalTable, Parameter


def get_param(key, default=0.0):
    p = Parameter.query.filter_by(key=key).first()
    return p.float_value() if p else default


def get_simples_rate(receita_12_meses):
    """Return Simples Nacional alíquota for a given 12-month revenue."""
    rows = SimplesNacionalTable.query.order_by(SimplesNacionalTable.min_revenue).all()
    for row in rows:
        if row.min_revenue <= receita_12_meses <= row.max_revenue:
            return row.rate
    if rows and receita_12_meses > rows[-1].max_revenue:
        return rows[-1].rate
    return 0.0


def calculate_dre(entry):
    """
    Compute full DRE from a DREEntry object.
    Returns a dict with all calculated values and percentages.
    """
    fat = entry.faturamento_bruto()

    # ── PARÂMETROS CONFIGURÁVEIS ────────────────────────────────────────────
    taxa_cartao_credito = get_param('taxa_cartao_credito', 0.01275)
    taxa_cartao_debito = get_param('taxa_cartao_debito', 0.002225)
    perc_fp_franquia = get_param('perc_fp_franquia', 0.012222)

    # Lucro Real rates
    lr_pis = get_param('lr_pis', 0.0165)
    lr_cofins = get_param('lr_cofins', 0.076)
    lr_irpj = get_param('lr_irpj', 0.15)
    lr_csll = get_param('lr_csll', 0.09)
    lr_irpj_adicional_rate = get_param('lr_irpj_adicional', 0.10)
    lr_irpj_adicional_threshold = get_param('lr_irpj_adicional_threshold', 20000.0)

    pct = lambda v: (v / fat * 100) if fat else 0

    # ── 2. IMPOSTOS ─────────────────────────────────────────────────────────
    if entry.regime_tributario == 'simples':
        receita_ref = entry.receita_12_meses if entry.receita_12_meses else fat * 12
        aliquota_simples = get_simples_rate(receita_ref)
        impostos = fat * aliquota_simples
        impostos_detail = {
            'simples_nacional': impostos,
            'aliquota_simples': aliquota_simples * 100,
        }
    else:  # lucro_real
        pis = fat * lr_pis
        cofins = fat * lr_cofins
        # IRPJ e CSLL calculados após CMV e despesas (previsão abaixo)
        impostos_receita = pis + cofins
        impostos_detail = {
            'pis': pis,
            'cofins': cofins,
            'lr_pis_rate': lr_pis * 100,
            'lr_cofins_rate': lr_cofins * 100,
        }
        impostos = impostos_receita  # IRPJ/CSLL adicionados depois

    receita_liquida = fat - impostos

    # ── 3. DESPESAS VARIÁVEIS - GERAIS ──────────────────────────────────────
    cartao_credito = (
        entry.cartao_credito_manual
        if entry.cartao_credito_manual is not None
        else fat * taxa_cartao_credito
    )
    cartao_debito = (
        entry.cartao_debito_manual
        if entry.cartao_debito_manual is not None
        else fat * taxa_cartao_debito
    )
    fp_franquia = fat * perc_fp_franquia

    dv_gerais = (
        entry.inadimplencia
        + entry.marketing_local
        + cartao_credito
        + cartao_debito
        + entry.embalagens_frete
        + entry.fretes_extras
        + entry.despesas_bancarias
        + fp_franquia
        + entry.dv_gerais_outros1
        + entry.dv_gerais_outros2
    )

    # ── 4. DESPESAS VARIÁVEIS - PESSOAL ─────────────────────────────────────
    dv_pessoal = (
        entry.salario_gerente
        + entry.salario_vendedores
        + entry.salario_supervisora
        + entry.salario_escritorio
        + entry.gincanas_premios
        + entry.fgts
        + entry.inss
        + entry.contrib_sindical
        + entry.encargos_outros
        + entry.vale_transporte
        + entry.vale_refeicao
        + entry.beneficios_outros
        + entry.decimo_terceiro
        + entry.ferias
        + entry.rescisoes
        + entry.pessoal_outros1
        + entry.pessoal_outros2
    )

    # ── 5. CMV + ROYALTIES ──────────────────────────────────────────────────
    cmv_total = (
        entry.cmv_tdb
        + entry.cmv_terceiros
        + entry.royalties
        + entry.diferencial_icms
    )

    # ── MARGEM DE CONTRIBUIÇÃO ──────────────────────────────────────────────
    total_dv = dv_gerais + dv_pessoal + cmv_total
    margem_contribuicao = receita_liquida - dv_gerais - dv_pessoal - cmv_total

    # ── 6. CUSTOS FIXOS ─────────────────────────────────────────────────────
    custos_fixos = (
        entry.pro_labore
        + entry.contabilidade
        + entry.limpeza
        + entry.software_microvix
        + entry.ecad
        + entry.sonorizacao
        + entry.pos_tef
        + entry.seguros
        + entry.manutencao_geral
        + entry.giver_omnichannel
        + entry.intranet
        + entry.qlik_sense
        + entry.internet
        + entry.telefonia
        + entry.aluguel_percentual
        + entry.aluguel_minimo
        + entry.condominio
        + entry.fp_shopping
        + entry.energia_eletrica
        + entry.ar_condicionado
        + entry.agua
        + entry.iptu
        + entry.outros_impostos_municipais
        + entry.papelaria
        + entry.provisao_inventario
        + entry.uniformes
        + entry.outros_gastos
        + entry.viagens_treinamentos
        + entry.cf_outros1
        + entry.cf_outros2
    )

    # ── 7. LUCRO LÍQUIDO ────────────────────────────────────────────────────
    lucro_liquido_antes_ir = margem_contribuicao - custos_fixos

    # Lucro Real: adicionar IRPJ e CSLL sobre lucro
    irpj = 0
    csll = 0
    if entry.regime_tributario == 'lucro_real':
        lucro_tributavel = max(lucro_liquido_antes_ir, 0)
        irpj = lucro_tributavel * lr_irpj
        adicional_base = max(lucro_tributavel - lr_irpj_adicional_threshold, 0)
        irpj += adicional_base * lr_irpj_adicional_rate
        csll = lucro_tributavel * lr_csll
        impostos_ir = irpj + csll
        impostos_detail['irpj'] = irpj
        impostos_detail['csll'] = csll
        impostos_detail['lr_irpj_rate'] = lr_irpj * 100
        impostos_detail['lr_csll_rate'] = lr_csll * 100
        impostos_total = impostos + impostos_ir
    else:
        impostos_total = impostos

    lucro_liquido = lucro_liquido_antes_ir - irpj - csll

    # ── DESCONTO ────────────────────────────────────────────────────────────
    desconto_valor = fat * (entry.desconto_percent / 100)
    lucro_apos_desconto = lucro_liquido + desconto_valor

    # ── 9. RESULTADO FINAL ──────────────────────────────────────────────────
    resultado_final = lucro_liquido - entry.retirada_socios

    # ── PONTO DE EQUILÍBRIO ─────────────────────────────────────────────────
    # PE = CF / (1 - (DV + CMV) / Fat)
    coef_dv = (dv_gerais + dv_pessoal + cmv_total + impostos_total) / fat if fat else 0
    margem_cobertura = 1 - coef_dv
    ponto_equilibrio = custos_fixos / margem_cobertura if margem_cobertura > 0 else 0

    # ── INDICADORES GERENCIAIS ──────────────────────────────────────────────
    ticket_medio = fat / entry.atendimentos if entry.atendimentos else 0
    pa = entry.pecas_vendidas / entry.atendimentos if entry.atendimentos else 0
    preco_medio = fat / entry.pecas_vendidas if entry.pecas_vendidas else 0
    lucratividade_pct = lucro_liquido / fat * 100 if fat else 0

    return {
        # Totais
        'faturamento_bruto': fat,
        'impostos': impostos_total,
        'impostos_detail': impostos_detail,
        'receita_liquida': receita_liquida,
        'dv_gerais': dv_gerais,
        'dv_pessoal': dv_pessoal,
        'cmv_total': cmv_total,
        'total_despesas_variaveis': total_dv,
        'margem_contribuicao': margem_contribuicao,
        'custos_fixos': custos_fixos,
        'lucro_liquido': lucro_liquido,
        'desconto_valor': desconto_valor,
        'lucro_apos_desconto': lucro_apos_desconto,
        'retirada_socios': entry.retirada_socios,
        'resultado_final': resultado_final,
        # Detalhe DV Gerais
        'cartao_credito': cartao_credito,
        'cartao_debito': cartao_debito,
        'fp_franquia': fp_franquia,
        # Indicadores
        'ponto_equilibrio': ponto_equilibrio,
        'ticket_medio': ticket_medio,
        'pa': pa,
        'preco_medio': preco_medio,
        'lucratividade_pct': lucratividade_pct,
        # Percentuais sobre faturamento
        'pct_impostos': pct(impostos_total),
        'pct_dv_gerais': pct(dv_gerais),
        'pct_dv_pessoal': pct(dv_pessoal),
        'pct_cmv': pct(cmv_total),
        'pct_margem': pct(margem_contribuicao),
        'pct_custos_fixos': pct(custos_fixos),
        'pct_lucro': lucratividade_pct,
    }


def calculate_annual_summary(entries):
    """Aggregate monthly DRE results into an annual summary."""
    if not entries:
        return None

    totals = {}
    keys = [
        'faturamento_bruto', 'impostos', 'receita_liquida',
        'dv_gerais', 'dv_pessoal', 'cmv_total',
        'margem_contribuicao', 'custos_fixos', 'lucro_liquido',
        'resultado_final', 'ponto_equilibrio',
    ]

    for key in keys:
        totals[key] = 0.0

    results = []
    for entry in entries:
        r = calculate_dre(entry)
        results.append({'month': entry.month, 'result': r})
        for key in keys:
            totals[key] += r.get(key, 0)

    fat = totals['faturamento_bruto']
    pct = lambda v: (v / fat * 100) if fat else 0
    totals['pct_impostos'] = pct(totals['impostos'])
    totals['pct_dv_gerais'] = pct(totals['dv_gerais'])
    totals['pct_dv_pessoal'] = pct(totals['dv_pessoal'])
    totals['pct_cmv'] = pct(totals['cmv_total'])
    totals['pct_margem'] = pct(totals['margem_contribuicao'])
    totals['pct_custos_fixos'] = pct(totals['custos_fixos'])
    totals['pct_lucro'] = pct(totals['lucro_liquido'])
    totals['lucratividade_pct'] = pct(totals['lucro_liquido'])
    totals['months_count'] = len(entries)

    return {'totals': totals, 'monthly': results}
