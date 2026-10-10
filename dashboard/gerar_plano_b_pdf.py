"""Plano B da entrega: dashboard estatico em PDF a partir dos 7 CSVs de outputs/.

Uso: python dashboard/gerar_plano_b_pdf.py
Saida: dashboard/plano_b_dashboard.pdf
"""
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "outputs"
PDF = Path(__file__).resolve().parent / "plano_b_dashboard.pdf"

AZUL, VERM, CINZA, VERDE = "#1f4e79", "#c0392b", "#9aa5b1", "#2e7d5b"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": .25, "figure.dpi": 150})

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, textColor=AZUL, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=ss["Normal"], fontSize=10, leading=13, textColor="#333333")
NOTA = ParagraphStyle("nota", parent=ss["Normal"], fontSize=7.5, leading=9.5, textColor="#666666")
CAPA = ParagraphStyle("capa", parent=ss["Title"], fontSize=26, textColor=AZUL)


def csv(nome):
    return pd.read_csv(OUT / nome, encoding="utf-8")


def img(fig, largura_cm, altura_cm):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=largura_cm * cm, height=altura_cm * cm)


def tabela(df, larguras=None, fonte=7.5, destaque=None):
    dados = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(dados, colWidths=larguras, repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL)),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
              ("FONTSIZE", (0, 0), (-1, -1), fonte),
              ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
              ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#c8d0d8")),
              ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for linha in destaque or []:
        estilo.append(("BACKGROUND", (0, linha + 1), (-1, linha + 1), colors.HexColor("#fde2de")))
    t.setStyle(TableStyle(estilo))
    return t


def pagina(titulo, subtitulo, *itens):
    return [Paragraph(titulo, H1), Paragraph(subtitulo, SUB), Spacer(1, .3 * cm), *itens, PageBreak()]


def br(v, casas=1):
    return f"{v:.{casas}f}".replace(".", ",")


# ---------------------------------------------------------------- P1
def p1():
    d = csv("p1_trajetoria_2015.csv")
    pior = d[d.maior_perda_anual].iloc[0]
    fig, ax = plt.subplots(figsize=(10, 4))
    x = d.ano_referencia
    ax.plot(x, d.tap_pct, marker="o", color=AZUL, label="TAP (permanência)")
    ax.plot(x, d.tda_pct, marker="o", color=VERM, label="TDA (desistência acum.)")
    ax.plot(x, d.tca_pct, marker="o", color=VERDE, label="TCA (conclusão acum.)")
    ax.axvspan(pior.ano_referencia - .4, pior.ano_referencia + .4, color=VERM, alpha=.1)
    ax.annotate(f"Maior perda anual: {br(pior.tada_pct, 2)}%\nno {int(pior.ano_do_curso)}º ano",
                (pior.ano_referencia, pior.tda_pct), (pior.ano_referencia - .9, pior.tda_pct + 14),
                arrowprops=dict(arrowstyle="->", color=VERM), color=VERM, fontweight="bold")
    ax.set_xticks(x)
    ax.set_ylabel("% dos ingressantes da coorte 2015")
    ax.legend(frameon=False, loc="upper right")
    t = d[["ano_referencia", "ano_do_curso", "tda_pct", "tca_pct", "tap_pct", "tada_pct"]].copy()
    t.columns = ["Ano", "Ano do curso", "TDA %", "TCA %", "TAP %", "Perda anual %"]
    t = t.round(2)
    return pagina(
        "P1 · Trajetória da coorte 2015 (Presencial, Mato Grosso)",
        f"Coorte de {int(d.qt_ingressantes.iloc[0]):,}".replace(",", ".")
        + f" ingressantes em {int(d.n_cursos.iloc[0])} cursos. "
        f"A maior perda anual ocorre no 2º ano ({br(pior.tada_pct, 2)}%). Em 2024, "
        f"{br(d.tda_pct.iloc[-1])}% desistiram e {br(d.tca_pct.iloc[-1])}% concluíram.",
        img(fig, 18, 7.2), Spacer(1, .2 * cm), tabela(t))


# ---------------------------------------------------------------- P2
def p2():
    d = csv("p2_ranking_desistencia.csv")
    d = d[d.nivel == "CINE_AREA_GERAL"]
    a20 = d[d.coorte == 2020].sort_values("tda_pct")
    a15 = d[d.coorte == 2015].set_index("no_cine_area_geral").tda_pct
    nomes = [n if len(n) < 38 else n[:36] + "…" for n in a20.no_cine_area_geral]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    cores = [VERM if i == len(a20) - 1 else CINZA for i in range(len(a20))]
    ax.barh(nomes, a20.tda_pct, color=cores, label="Coorte 2020")
    ax.scatter([a15.get(n) for n in a20.no_cine_area_geral], nomes, color=AZUL, zorder=3,
               s=22, label="Coorte 2015")
    for i, v in enumerate(a20.tda_pct):
        ax.text(v + .8, i, f"{br(v)}%", va="center", fontsize=8)
    ax.set_xlabel("TDA no 5º ano (%)")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", alpha=0)
    t = a20.sort_values("ranking_desistencia")[["ranking_desistencia", "no_cine_area_geral", "n_cursos",
                                                 "qt_ingressantes", "tda_pct"]].round(2)
    t.columns = ["#", "Área geral CINE (coorte 2020)", "Cursos", "Ingressantes", "TDA 5º ano %"]
    topo = a20.iloc[-1]
    return pagina(
        "P2 · Ranking de desistência no 5º ano por área geral CINE",
        f"Na coorte 2020, <b>{topo.no_cine_area_geral}</b> lidera com {br(topo.tda_pct)}% de desistência acumulada "
        "no 5º ano. Pontos azuis: mesma área na coorte 2015.",
        img(fig, 18, 8.3), Spacer(1, .2 * cm), tabela(t, [1 * cm, 9 * cm, 2 * cm, 3 * cm, 3 * cm]))


# ---------------------------------------------------------------- P3
def p3():
    d = csv("p3_evasao_censo.csv")
    ano = int(d.nu_ano_censo.max())
    a = d[d.nu_ano_censo == ano]
    redes = list(a.grupo_rede.unique())
    fig, ax = plt.subplots(figsize=(10, 4))
    w = .38
    for j, (mod, cor) in enumerate([("Presencial", AZUL), ("EAD", VERM)]):
        s = a[a.modalidade == mod].set_index("grupo_rede").evasao_anual_pct.reindex(redes)
        b = ax.bar([i + (j - .5) * w for i in range(len(redes))], s, w, color=cor, label=mod)
        for r, v in zip(b, s):
            ax.text(r.get_x() + w / 2, v + .6, f"{br(v)}%", ha="center", fontsize=8,
                    fontweight="bold" if v == a.evasao_anual_pct.max() else None)
    ax.set_xticks(range(len(redes)), redes)
    ax.set_ylabel(f"Evasão anual {ano} (%)")
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0)
    p = d.pivot_table(index=["grupo_rede", "modalidade"], columns="nu_ano_censo",
                      values="evasao_anual_pct").round(1).reset_index()
    p.columns = ["Rede", "Modalidade"] + [str(c) for c in p.columns[2:]]
    mx = a.loc[a.evasao_anual_pct.idxmax()]
    return pagina(
        "P3 · Evasão anual: rede (pública × privada) e modalidade (presencial × EAD)",
        f"Em {ano}, o maior índice é <b>{mx.grupo_rede} · {mx.modalidade}</b>: {br(mx.evasao_anual_pct)}% "
        "(desvinculados ÷ matrículas + desvinculados + transferidos). Tabela: série 2021-2024.",
        img(fig, 18, 7.2), Spacer(1, .2 * cm), tabela(p, [6 * cm, 3 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm]))


# ---------------------------------------------------------------- P4
def p4():
    d = csv("p4_cpc_vs_desistencia.csv")
    f = d[d.agrupamento == "CPC_FAIXA"]
    pe = d.corr_pearson_cpc_tda.iloc[0]
    sp = d.corr_spearman_cpc_tda.iloc[0]
    fig, ax = plt.subplots(figsize=(10, 4))
    b = ax.bar([f"Faixa {g}\n(n={n})" for g, n in zip(f.grupo, f.n_cursos)], f.tda_pct, color=AZUL)
    for r, v in zip(b, f.tda_pct):
        ax.text(r.get_x() + r.get_width() / 2, v + .8, f"{br(v)}%", ha="center", fontsize=9)
    ax.set_ylabel("TDA acumulada (%)")
    ax.set_ylim(0, f.tda_pct.max() * 1.2)
    ax.grid(axis="x", alpha=0)
    ax.set_title(f"Correlação CPC × TDA: Pearson {br(pe, 3)} · Spearman {br(sp, 3)} "
                 f"({int(d.n_cursos_correlacao.iloc[0])} cursos)", fontsize=10, color=VERM, loc="left")
    t = f[["grupo", "n_cursos", "qt_ingressantes", "cpc_continuo_medio", "tda_pct"]].round(2)
    t.columns = ["Faixa CPC", "Cursos", "Ingressantes", "CPC médio", "TDA %"]
    return pagina(
        "P4 · Qualidade do curso (CPC) × desistência acumulada",
        f"Correlação fraca (Pearson {br(pe, 3)}): o CPC, isoladamente, explica pouco da desistência. "
        "Faixas 1 e 5 têm poucos cursos (leitura cautelosa). Associação, não causalidade.",
        img(fig, 18, 7.2), Spacer(1, .2 * cm), tabela(t, [3 * cm, 2.5 * cm, 3.5 * cm, 3 * cm, 3 * cm]))


# ---------------------------------------------------------------- P5
def p5():
    d = csv("p5_funil_licenciaturas.csv")
    crit = d[d.funil_critico].sort_values("tda_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 3.9))
    ax.scatter(d[~d.funil_critico].tda_pct, d[~d.funil_critico].prop_proficiente_pct, color=CINZA, label="Demais")
    ax.scatter(crit.tda_pct, crit.prop_proficiente_pct, color=VERM, label="Funil crítico")
    ax.axvline(d.tda_pct.median(), color=AZUL, ls="--", lw=1)
    ax.axhline(d.prop_proficiente_pct.median(), color=AZUL, ls="--", lw=1)
    ax.set_xlabel("TDA da coorte de ingresso (%)")
    ax.set_ylabel("Concluintes proficientes no Enade (%)")
    ax.legend(frameon=False)
    t = crit[["no_area_avaliacao", "sg_ies", "no_municipio", "no_modalidade_ensino", "qt_ingressantes",
              "tda_pct", "prop_proficiente_pct", "estimativa_proficientes_por_100_ingressantes"]].round(1)
    t["no_area_avaliacao"] = t.no_area_avaliacao.str.slice(0, 26)
    t.columns = ["Licenciatura", "IES", "Município", "Modalidade", "Ingress.", "TDA %",
                 "Profic. %", "Profic./100 ingr."]
    return pagina(
        f"P5 · Funil das licenciaturas: {len(crit)} de {len(d)} cursos em situação crítica",
        "Crítico = desistência igual ou acima da mediana e proficiência Enade abaixo da mediana. "
        "Linhas tracejadas: medianas do conjunto.",
        img(fig, 12.5, 4.9), Spacer(1, .1 * cm),
        tabela(t, [4.6 * cm, 2 * cm, 3.4 * cm, 2.4 * cm, 1.8 * cm, 1.6 * cm, 1.8 * cm, 2.6 * cm], fonte=6.5))


# ---------------------------------------------------------------- B1
def b1():
    d = csv("b1_desertos_ensino_superior.csv")
    des = d[d.deserto]
    pop = int(des.pop_18_24.sum())
    tot = int(d.pop_18_24.sum())
    top = des.sort_values("pop_18_24", ascending=False).head(12)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.barh(top.no_municipio[::-1], top.pop_18_24[::-1], color=VERM)
    ax.set_xlabel("População de 18 a 24 anos (IBGE)")
    ax.grid(axis="y", alpha=0)
    kpi = Table([[f"{len(des)}", f"{len(d)}", f"{pop:,}".replace(",", "."), f"{br(pop / tot * 100)}%"],
                 ["municípios desertos", "municípios analisados", "jovens 18-24 impactados",
                  "da população jovem de MT"]], colWidths=[4.4 * cm] * 4)
    kpi.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, 0), 20), ("FONTSIZE", (0, 1), (-1, 1), 8),
                             ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(VERM)),
                             ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                             ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#c8d0d8")),
                             ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#e3e8ee"))]))
    t = top[["no_municipio", "pop_18_24", "n_cursos_presenciais", "n_ies", "vagas_presenciais_2024"]]
    t.columns = ["Município", "Pop. 18-24", "Cursos presenciais", "IES", "Vagas 2024"]
    return pagina(
        "B1 · Desertos de ensino superior em Mato Grosso",
        "Deserto = município com 0 vaga presencial em 2024 (sql/06_b1_desertos.sql); população jovem de 18 a 24 anos (IBGE). Top 12 desertos por população jovem.",
        kpi, Spacer(1, .3 * cm), img(fig, 17, 6.4), Spacer(1, .1 * cm),
        tabela(t, [5 * cm, 3 * cm, 3.6 * cm, 2 * cm, 3 * cm]))


# ---------------------------------------------------------------- B2
def b2():
    d = csv("b2_financiamento_permanencia.csv")
    t = d[["nu_ano_censo", "modalidade", "grupo_adesao", "n_cursos", "prop_financiados_pct",
           "evasao_anual_pct", "dif_evasao_pp_vs_baixa_adesao"]].copy()
    t["evasao_anual_pct"] = t.evasao_anual_pct.round(1)
    t["dif_evasao_pp_vs_baixa_adesao"] = t.dif_evasao_pp_vs_baixa_adesao.round(1)
    t.columns = ["Ano", "Modalidade", "Grupo de adesão", "Cursos", "% financiados", "Evasão %",
                 "Dif. vs baixa adesão (p.p.)"]
    alta = d[d.grupo_adesao.str.startswith("Alta")]
    media = alta.groupby("modalidade").dif_evasao_pp_vs_baixa_adesao.mean().round(1)
    return pagina(
        "B2 · Adesão ao financiamento × taxa de evasão (2021-2024)",
        "Cursos com adesão ≥ 10% de ingressantes financiados vs. < 10%. Diferença média (alta − baixa adesão): "
        + "; ".join(f"{m} {br(v)} p.p." for m, v in media.items())
        + " O sinal é inconsistente entre anos e modalidades.",
        tabela(t, [1.6 * cm, 2.6 * cm, 4.6 * cm, 1.8 * cm, 2.6 * cm, 2.2 * cm, 4.2 * cm], fonte=8),
        Spacer(1, .3 * cm),
        Paragraph("Associação observacional, sem inferência causal: não controla perfil do aluno, curso ou IES.",
                  NOTA))


def main():
    doc = SimpleDocTemplate(str(PDF), pagesize=landscape(A4), leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.2 * cm,
                            title="Rota do Diploma - Plano B", author="Grupo 6 · DataHack UNIVAG 2026")
    capa = [Spacer(1, 4 * cm), Paragraph("Rota do Diploma", CAPA),
            Paragraph("Plano B · Dashboard estático (PDF) · DataHack UNIVAG 2026 · Grupo 6", SUB),
            Spacer(1, .6 * cm),
            Paragraph("Perguntas P1-P5 e bônus B1-B2 sobre trajetória, evasão e qualidade da educação superior "
                      "em Mato Grosso. Fontes: INEP (Censo da Educação Superior, CPC, Enade) e IBGE (SIDRA 9514). "
                      "Todas as séries são lidas diretamente dos CSVs em outputs/.", SUB),
            PageBreak()]
    doc.build(capa + p1() + p2() + p3() + p4() + p5() + b1() + b2()[:-1])
    print(f"PDF gerado: {PDF}")


if __name__ == "__main__":
    main()
