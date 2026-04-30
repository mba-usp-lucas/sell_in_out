"""
Alcon Sales Insights - Gerador de HTML standalone (v5.4)
Dashboard analitico com Sell-in + Sell-out gerencial
============================================================
v5.4: Adiciona leitura de sell-out gerencial (formato wide com meses em colunas)

COMO USAR
---------
1. pip install pandas openpyxl
2. Ajustar PATHs abaixo
3. Ter 'dashboard_template_v5.html' na mesma pasta
4. python gerar_dashboard_v5.py

NOTA: Sell-out e OPCIONAL. Se o arquivo nao existir, o card resumo mostra "—".
"""

from pathlib import Path
import pandas as pd
import json
import re
from datetime import datetime

# =========================================================
# CONFIGURACAO - AJUSTE AQUI
# =========================================================
PATH_XLSX = r"C:\Users\PEREILU3\OneDrive - Alcon\AdHoc_IC\Projeto\INSIGHTS\f_SELLIN.xlsx"
PATH_TARGETS = r"C:\Users\PEREILU3\OneDrive - Alcon\AdHoc_IC\Projeto\INSIGHTS\Targets.xlsx"
PATH_TARGETS_FIN = r"C:\Users\PEREILU3\OneDrive - Alcon\AdHoc_IC\Projeto\INSIGHTS\Targets_Financeiros.xlsx"
PATH_SELLOUT = r"C:\Users\PEREILU3\OneDrive - Alcon\AdHoc_IC\Projeto\INSIGHTS\f_SELLOUT_GERENCIAL.xlsx"
PATH_OUTPUT = r"dashboard_alcon_sales_insights.html"
PATH_TEMPLATE = r"dashboard_template_v5.html"

COLS = {
    "ANO": "ANO",
    "MES_NUM": "MES_NUM",
    "CLIENTE": "GRUPO_CLIENTE_FINAL",
    "TIPO_CLIENTE": "TIPO_CLIENTE_FINAL",
    "FRANQUIA": "FRANQUIA",
    "PRODUTO": "PRODUTO",
    "FONTE": "FONTE",
    "VALOR_UNID": "Vendas_Unid",
    "VALOR_BRL": "Vendas_BRL",
    "VALOR_USD": "Vendas_USD",
    "MOEDA": None,
}

# =========================================================
# CONFIGURACAO SELL-OUT - AJUSTE OS NOMES SE FOREM DIFERENTES
# =========================================================
COLS_SELLOUT = {
    "GRUPO_PAINEL": "GRUPO_PAINEL",
    "FRANQUIA": "FRANQUIA",
    "TIPO_CLIENTE": "TIPO_CLIENTE",
    "PRODUTO": "PROD_DESC",
    "MEDIDA": "MEDIDA",
    "CHAN_DESC": "CHAN_DESC",  # canal: Farmacia / Hospitalar / Outros / Transferencias
}
MEDIDA_REAIS = "Reais_PPP"
MEDIDA_UNID = "Unidades"

# Filtro padrao do canal - aplicado SEMPRE no agregado de sell-out
# Mantem apenas linhas onde CHAN_DESC contem 'farmacia' (case insensitive)
# Distribuidor pode aparecer com sub-canais: 'Farmacia' (mantem), 'Hospitalar', 'Outros canais', 'Transferencias' (descarta)
FILTRO_CANAL_PADRAO = "farmacia"


def ler_sellout_gerencial(path):
    """Le arquivo wide e converte para long agregado.

    IMPORTANTE: aplica filtro CHAN_DESC contendo 'farmacia' (default fixo).
    Hospitalar, Outros canais e Transferencias sao excluidos.
    """
    if not Path(path).exists():
        print(f"[INFO] Sell-out nao encontrado em {path} - sera ignorado")
        return [], None

    print(f"[OK] Lendo sell-out: {path}")
    df = pd.read_excel(path)
    print(f"     Linhas raw: {len(df)}")

    cols_meses = [c for c in df.columns if re.match(r"^\d{4}_\d{2}_\d{2}$", str(c))]
    print(f"     Colunas de mes encontradas: {len(cols_meses)}")

    if len(cols_meses) == 0:
        print("[ERRO] Nenhuma coluna no formato YYYY_MM_DD. Sell-out ignorado.")
        return [], None

    for k, col_name in COLS_SELLOUT.items():
        if col_name not in df.columns:
            # CHAN_DESC pode nao existir em arquivos antigos - apenas avisa
            if k == "CHAN_DESC":
                print(f"[AVISO] Coluna '{col_name}' nao encontrada - filtro de canal nao sera aplicado")
                continue
            print(f"[ERRO] Coluna '{col_name}' nao encontrada. Ajuste COLS_SELLOUT no codigo.")
            return [], None

    # Aplicar filtro padrao: apenas farmacia (case insensitive)
    if COLS_SELLOUT["CHAN_DESC"] in df.columns:
        antes = len(df)
        df = df[df[COLS_SELLOUT["CHAN_DESC"]].astype(str).str.contains(FILTRO_CANAL_PADRAO, case=False, na=False)].copy()
        depois = len(df)
        print(f"     Filtro canal padrao 'farmacia': {antes:,} -> {depois:,} linhas ({100*depois/antes:.1f}%)")

    cols_id = [
        COLS_SELLOUT["GRUPO_PAINEL"],
        COLS_SELLOUT["FRANQUIA"],
        COLS_SELLOUT["TIPO_CLIENTE"],
        COLS_SELLOUT["PRODUTO"],
        COLS_SELLOUT["MEDIDA"],
    ]
    df = df[cols_id + cols_meses].copy()

    df_long = df.melt(
        id_vars=cols_id,
        value_vars=cols_meses,
        var_name="DATA_RAW",
        value_name="VALOR",
    )

    df_long["VALOR"] = pd.to_numeric(df_long["VALOR"], errors="coerce").fillna(0)
    df_long = df_long[df_long["VALOR"] > 0]

    df_long["ANO"] = df_long["DATA_RAW"].str[:4].astype(int)
    df_long["MES"] = df_long["DATA_RAW"].str[5:7].astype(int)
    df_long = df_long.drop(columns=["DATA_RAW"])

    df_pivot = df_long.pivot_table(
        index=[
            COLS_SELLOUT["GRUPO_PAINEL"],
            COLS_SELLOUT["FRANQUIA"],
            COLS_SELLOUT["TIPO_CLIENTE"],
            COLS_SELLOUT["PRODUTO"],
            "ANO",
            "MES",
        ],
        columns=COLS_SELLOUT["MEDIDA"],
        values="VALOR",
        aggfunc="sum",
    ).reset_index()

    df_pivot.columns.name = None
    if MEDIDA_REAIS in df_pivot.columns:
        df_pivot = df_pivot.rename(columns={MEDIDA_REAIS: "BRL"})
    else:
        df_pivot["BRL"] = 0
    if MEDIDA_UNID in df_pivot.columns:
        df_pivot = df_pivot.rename(columns={MEDIDA_UNID: "UNID"})
    else:
        df_pivot["UNID"] = 0

    df_pivot["BRL"] = df_pivot["BRL"].fillna(0)
    df_pivot["UNID"] = df_pivot["UNID"].fillna(0)

    df_pivot = df_pivot.rename(columns={
        COLS_SELLOUT["GRUPO_PAINEL"]: "GRUPO_PAINEL",
        COLS_SELLOUT["FRANQUIA"]: "FRANQUIA",
        COLS_SELLOUT["TIPO_CLIENTE"]: "TIPO_CLIENTE",
        COLS_SELLOUT["PRODUTO"]: "PRODUTO",
    })

    ultimo_mes = df_pivot.sort_values(["ANO", "MES"], ascending=False).iloc[0]
    ultimo_periodo = {"ano": int(ultimo_mes["ANO"]), "mes": int(ultimo_mes["MES"])}

    print(f"     Linhas agregadas: {len(df_pivot):,}")
    print(f"     Ultimo periodo: {ultimo_periodo['mes']:02d}/{ultimo_periodo['ano']}")
    print(f"     Total BRL: R$ {df_pivot['BRL'].sum():,.0f}")
    print(f"     Total Unid: {df_pivot['UNID'].sum():,.0f}")

    registros = df_pivot.to_dict("records")
    return registros, ultimo_periodo


def ler_sellin(path):
    """Le sell-in"""
    print(f"[OK] Lendo sell-in: {path}")
    df = pd.read_excel(path)
    print(f"     Linhas: {len(df):,}")

    obrig = ["ANO", "MES_NUM"]
    for c in obrig:
        if c not in df.columns:
            raise ValueError(f"Coluna obrigatoria '{c}' ausente em {path}")

    for c in ["Vendas_Unid", "Vendas_BRL", "Vendas_USD"]:
        if c not in df.columns:
            df[c] = 0

    for c, default in [
        ("GRUPO_CLIENTE_FINAL", "—"),
        ("TIPO_CLIENTE_FINAL", "—"),
        ("FRANQUIA", "—"),
        ("PRODUTO", "—"),
        ("FONTE", "—"),
    ]:
        if c not in df.columns:
            df[c] = default

    return df


def ler_targets(path):
    if not Path(path).exists():
        return {}
    df = pd.read_excel(path)
    if "PRODUTO" not in df.columns or "TARGET_PCT" not in df.columns:
        return {}
    if "FLAG" in df.columns:
        df_foco = df[df["FLAG"].astype(str).str.upper() == "FOCO"]
    else:
        df_foco = df
    targets = {}
    for _, row in df_foco.iterrows():
        produto = str(row["PRODUTO"]).strip()
        targets[produto] = float(row["TARGET_PCT"])
    print(f"[OK] {len(targets)} targets FOCO carregados")
    return targets


def ler_targets_fin(path):
    if not Path(path).exists():
        return []
    df = pd.read_excel(path)
    cols_obrig = ["FRANQUIA", "PRODUTO", "ANO", "MES_NUM"]
    if not all(c in df.columns for c in cols_obrig):
        return []
    for c in ["TARGET_BRL", "TARGET_UNID"]:
        if c not in df.columns:
            df[c] = 0
    print(f"[OK] {len(df)} targets financeiros carregados")
    return df.to_dict("records")


def gerar_html():
    df = ler_sellin(PATH_XLSX)
    targets = ler_targets(PATH_TARGETS)
    targets_fin = ler_targets_fin(PATH_TARGETS_FIN)
    sellout, ultimo_sellout = ler_sellout_gerencial(PATH_SELLOUT)

    template = Path(PATH_TEMPLATE).read_text(encoding="utf-8")

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    dados_json = json.dumps(df.to_dict("records"), ensure_ascii=False, default=str)
    cols_json = json.dumps(COLS, ensure_ascii=False)
    targets_json = json.dumps(targets, ensure_ascii=False)
    targets_fin_json = json.dumps(targets_fin, ensure_ascii=False, default=str)
    sellout_json = json.dumps(sellout, ensure_ascii=False, default=str)
    ultimo_sellout_json = json.dumps(ultimo_sellout, ensure_ascii=False) if ultimo_sellout else "null"

    print(f"\nJSON sell-in: {len(dados_json)/1024:.1f} KB")
    print(f"JSON sell-out: {len(sellout_json)/1024:.1f} KB")

    padrao_cols = re.compile(r"const\s+COLS\s*=\s*\{[^}]+\};", re.DOTALL)
    novo_template, n_cols = padrao_cols.subn(
        "const COLS = window.__ALCON_COLS_EMBED__;",
        template, count=1
    )
    if n_cols == 0:
        raise ValueError("Nao achei o bloco 'const COLS = {...}' no template.")
    template = novo_template

    marcador = "const COLS = window.__ALCON_COLS_EMBED__;"
    script_injecao = (
        f"window.__ALCON_DATA_EMBED__ = {dados_json};\n"
        f"window.__ALCON_COLS_EMBED__ = {cols_json};\n"
        f"window.__ALCON_TARGETS_EMBED__ = {targets_json};\n"
        f"window.__ALCON_TARGETS_FIN_EMBED__ = {targets_fin_json};\n"
        f"window.__ALCON_SELLOUT_EMBED__ = {sellout_json};\n"
        f"window.__ALCON_SELLOUT_ULTIMO__ = {ultimo_sellout_json};\n"
        f"window.__ALCON_META_EMBED__ = {{ registros: {len(df)}, sellout_registros: {len(sellout)}, timestamp: \"{timestamp}\" }};\n"
        f"{marcador}"
    )
    template = template.replace(marcador, script_injecao, 1)

    padrao_init = re.compile(r"rawData\s*=\s*gerarDadosExemplo\(\)\s*;", re.DOTALL)
    init_novo = (
        "rawData = window.__ALCON_DATA_EMBED__.map(function(r){"
        "return Object.assign({}, r, {"
        "[COLS.ANO]: +r[COLS.ANO],"
        "[COLS.MES_NUM]: +r[COLS.MES_NUM],"
        "[COLS.VALOR_UNID]: +r[COLS.VALOR_UNID] || 0,"
        "[COLS.VALOR_BRL]: +r[COLS.VALOR_BRL] || 0,"
        "[COLS.VALOR_USD]: +r[COLS.VALOR_USD] || 0,"
        "[COLS.TIPO_CLIENTE]: r[COLS.TIPO_CLIENTE] || '-'"
        "});});"
        "if(window.__ALCON_TARGETS_EMBED__){mapTargets = window.__ALCON_TARGETS_EMBED__;}"
        "if(window.__ALCON_TARGETS_FIN_EMBED__){targetsFinanceiros = window.__ALCON_TARGETS_FIN_EMBED__;}"
        "if(window.__ALCON_SELLOUT_EMBED__){rawDataSellout = window.__ALCON_SELLOUT_EMBED__.map(function(r){return Object.assign({},r,{ANO:+r.ANO,MES:+r.MES,BRL:+r.BRL||0,UNID:+r.UNID||0});});}"
        "if(window.__ALCON_SELLOUT_ULTIMO__){selloutUltimoPeriodo = window.__ALCON_SELLOUT_ULTIMO__;}"
    )
    novo_template2, n2 = padrao_init.subn(init_novo, template, count=1)

    if n2 == 0:
        raise ValueError("Nao achei 'rawData = gerarDadosExemplo()'.")
    template = novo_template2

    padrao_func = re.compile(
        r"function\s+gerarDadosExemplo\s*\(\s*\)\s*\{.*?^\}",
        re.DOTALL | re.MULTILINE
    )
    template = padrao_func.sub("// gerarDadosExemplo() removida - dados embutidos via Python", template, count=1)

    status_msg = f"{len(df):,} registros sell-in"
    if sellout:
        status_msg += f" + {len(sellout):,} sell-out"
    if targets:
        status_msg += f" + {len(targets)} targets FOCO"
    status_msg += f" - {timestamp}"

    template = template.replace(
        "<span id=\"statusText\">Carregando...</span>",
        f"<span id=\"statusText\">{status_msg}</span>"
    )

    Path(PATH_OUTPUT).write_text(template, encoding="utf-8")
    print(f"\n[OK] Gerado: {PATH_OUTPUT} ({len(template)/1024/1024:.2f} MB)")
    print(f"=" * 60)
    print(f"Pronto! Arquivo: {PATH_OUTPUT}")
    print(f"=" * 60)


if __name__ == "__main__":
    gerar_html()
