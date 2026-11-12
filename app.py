from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = Path.cwd()
CSV_DIR = BASE_DIR / "CSV"
IGNORE_DIRS = {"debug", "__pycache__"}


def localizar_csvs() -> list[Path]:
    arquivos: list[Path] = []
    vistos: set[str] = set()
    roots = [CSV_DIR, BASE_DIR, WORK_DIR]

    for base in roots:
        if not base.exists():
            continue
        for arquivo in base.rglob("*.csv"):
            if arquivo.is_file():
                if any(part in IGNORE_DIRS for part in arquivo.parts):
                    continue
                resolved = str(arquivo.resolve())
                if resolved not in vistos:
                    vistos.add(resolved)
                    arquivos.append(arquivo)

    return sorted(arquivos, key=lambda p: p.name.lower())


CSV_FILES = localizar_csvs()


def ler_csv_robusto(caminho: Path) -> pd.DataFrame | None:
    """Tenta ler um CSV usando vários delimitadores e encodings, com limite de linhas para manter o dashboard leve."""
    encodings = ["utf-8-sig", "latin1", "cp1252"]
    separators = [None, ";", ",", "\t"]

    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(
                    caminho,
                    sep=sep,
                    encoding=encoding,
                    engine="python",
                    on_bad_lines="skip",
                    nrows=50000,
                    dtype=str,
                )
                if df.empty:
                    continue
                if df.shape[1] <= 1 and sep is None:
                    continue
                return df
            except Exception:
                continue

    try:
        with open(caminho, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            sample = fh.read(20000)
        if not sample.strip():
            return None
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        df = pd.read_csv(
            caminho,
            sep=dialect.delimiter,
            encoding="utf-8-sig",
            engine="python",
            on_bad_lines="skip",
            nrows=50000,
            dtype=str,
        )
        if not df.empty and df.shape[1] > 1:
            return df
    except Exception:
        return None

    return None


@st.cache_data
def carregar_datasets() -> dict[str, pd.DataFrame]:
    """Lê todos os CSVs do diretório e devolve um dicionário com nome e dataframe."""
    datasets: dict[str, pd.DataFrame] = {}

    for arquivo in CSV_FILES:
        df = ler_csv_robusto(arquivo)
        if df is not None and not df.empty:
            datasets[arquivo.name] = df

    return datasets


def normalizar_nome(nome: str) -> str:
    texto = re.sub(r"[^a-zA-Z0-9]", "", str(nome).upper())
    return texto


def extrair_ano(valor: object) -> object:
    if pd.isna(valor):
        return None
    texto = str(valor)
    match = re.search(r"(20\d{2}|19\d{2})", texto)
    if match:
        return int(match.group(1))
    return None


def encontrar_coluna(df: pd.DataFrame, aliases: list[str]) -> str | None:
    aliases_norm = {normalizar_nome(alias) for alias in aliases}
    for col in df.columns:
        if normalizar_nome(col) in aliases_norm:
            return col
    return None


def transformar_para_master(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for nome_arquivo, df in datasets.items():
        if df.empty:
            continue

        df2 = df.copy()
        df2.columns = [str(c) for c in df2.columns]

        for col in list(df2.columns):
            df2 = df2.rename(columns={col: str(col).strip()})

        if "ano" not in df2.columns and "NU_ANO" not in df2.columns and "ANO" not in df2.columns:
            if "ANO" not in df2.columns:
                df2["ano"] = extrair_ano(nome_arquivo)

        ano_col = encontrar_coluna(df2, ["NU_ANO", "ANO", "ANO_PROVA", "ANO_REALIZACAO"])
        if ano_col is not None:
            df2["ano"] = pd.to_numeric(df2[ano_col], errors="coerce")
        else:
            df2["ano"] = extrair_ano(nome_arquivo)

        uf_col = encontrar_coluna(df2, ["NO_UF_PROVA", "SG_UF_PROVA", "UF", "NO_UF_ESC", "SG_UF_ESC", "UF_ESC"])
        if uf_col is not None:
            df2["uf"] = df2[uf_col].astype(str)
        else:
            df2["uf"] = "Não informado"

        sexo_col = encontrar_coluna(df2, ["TP_SEXO", "SEXO", "GENERO", "NO_SEXO"])
        if sexo_col is not None:
            df2["sexo"] = df2[sexo_col].astype(str)
        else:
            df2["sexo"] = "Não informado"

        nota_cols = {
            "nota_matematica": ["NU_NOTA_MT", "NOTA_MT", "MATEMATICA"],
            "nota_ciencias_naturais": ["NU_NOTA_CN", "NOTA_CN", "CIENCIAS_NATURAIS"],
            "nota_ciencias_humanas": ["NU_NOTA_CH", "NOTA_CH", "CIENCIAS_HUMANAS"],
            "nota_linguagens": ["NU_NOTA_LC", "NOTA_LC", "LINGUAGENS"],
            "nota_redacao": ["NU_NOTA_REDACAO", "NOTA_REDACAO", "REDACAO"],
        }

        for nome_meta, aliases in nota_cols.items():
            col = encontrar_coluna(df2, aliases)
            if col is not None:
                df2[nome_meta] = pd.to_numeric(df2[col], errors="coerce")
            else:
                df2[nome_meta] = pd.NA

        notas_validas = [
            col for col in [
                "nota_matematica",
                "nota_ciencias_naturais",
                "nota_ciencias_humanas",
                "nota_linguagens",
                "nota_redacao",
            ]
            if col in df2.columns
        ]

        if notas_validas:
            df2["nota_media_geral"] = df2[notas_validas].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        else:
            df2["nota_media_geral"] = pd.NA

        df2["arquivo_origem"] = nome_arquivo
        frames.append(df2)

    if not frames:
        return pd.DataFrame()

    master = pd.concat(frames, ignore_index=True)
    if "ano" in master.columns:
        master["ano"] = pd.to_numeric(master["ano"], errors="coerce")
    if "uf" in master.columns:
        master["uf"] = master["uf"].fillna("Não informado").astype(str)
    if "sexo" in master.columns:
        master["sexo"] = master["sexo"].fillna("Não informado").astype(str)
    if "nota_media_geral" in master.columns:
        master["nota_media_geral"] = pd.to_numeric(master["nota_media_geral"], errors="coerce")
    return master


def aplicar_filtros(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return master

    anos = sorted(pd.to_numeric(master["ano"], errors="coerce").dropna().astype(int).unique().tolist()) if "ano" in master.columns else []
    ufs = sorted(master["uf"].dropna().unique().tolist()) if "uf" in master.columns else []
    sexos = sorted(master["sexo"].dropna().unique().tolist()) if "sexo" in master.columns else []

    ano_sel = st.sidebar.multiselect("Ano", anos, default=anos)
    uf_sel = st.sidebar.multiselect("UF", ufs, default=[])
    sexo_sel = st.sidebar.multiselect("Sexo", sexos, default=[])

    mask = pd.Series(True, index=master.index)
    if ano_sel:
        mask &= master["ano"].isin(ano_sel)
    filtro = master.loc[mask].copy()

    if uf_sel:
        filtro = filtro[filtro["uf"].isin(uf_sel)]
    if sexo_sel:
        filtro = filtro[filtro["sexo"].isin(sexo_sel)]

    return filtro.reset_index(drop=True)


def criar_metricas(df: pd.DataFrame):
    col1, col2, col3, col4 = st.columns(4)

    registros = len(df)
    if "nota_media_geral" in df.columns:
        notas = pd.to_numeric(df["nota_media_geral"], errors="coerce").dropna()
        media = f"{notas.mean():.2f}" if not notas.empty else "N/A"
    else:
        notas = pd.Series(dtype=float)
        media = "N/A"

    with col1:
        st.metric("Registros", f"{registros:,}")
    with col2:
        st.metric("Média geral", media)
    with col3:
        top_uf = df["uf"].str.upper().replace("NÃO INFORMADO", "Não informado") if "uf" in df.columns else pd.Series([], dtype=str)
        melhor_uf = top_uf.mode().iloc[0] if not top_uf.empty else "N/A"
        st.metric("UF mais frequente", melhor_uf)
    with col4:
        sexo_mais_frequente = df["sexo"].mode().iloc[0] if "sexo" in df.columns and not df.empty else "N/A"
        st.metric("Sexo mais comum", sexo_mais_frequente)


def main() -> None:
    st.set_page_config(page_title="Dashboard ENEM & Estude", layout="wide")
    st.title("📊 Dashboard ENEM & Estude")
    st.caption("Exploração interativa dos arquivos CSV do ENEM e dados complementares do projeto.")

    datasets = carregar_datasets()

    if not datasets:
        arquivos = localizar_csvs()
        nomes = [p.name for p in arquivos[:20]]
        st.error(f"Nenhum CSV foi carregado. Arquivos encontrados no projeto: {len(arquivos)}")
        if nomes:
            st.write(nomes)
        return

    master = transformar_para_master(datasets)

    if master.empty:
        st.warning("Os arquivos CSV foram encontrados, mas nenhum campo compatível com o ENEM foi reconhecido.")
        st.json({"arquivos": list(datasets.keys())})
        return

    filtered = aplicar_filtros(master)

    if filtered.empty:
        st.warning("Nenhum registro atende aos filtros selecionados.")
        return

    criar_metricas(filtered)

    if "nota_media_geral" not in filtered.columns:
        st.warning("A base carregada não possui a coluna de média geral, então os gráficos de desempenho estão indisponíveis.")
        st.stop()

    st.subheader("📈 Evolução da nota média por ano")
    serie_ano = (
        filtered.groupby("ano", as_index=False)["nota_media_geral"]
        .mean()
        .sort_values("ano")
    )
    fig_linha = px.line(
        serie_ano,
        x="ano",
        y="nota_media_geral",
        markers=True,
        title="Nota média por ano",
        labels={"ano": "Ano", "nota_media_geral": "Nota média geral"},
    )
    st.plotly_chart(fig_linha, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Top UFs por nota média")
        uf_media = (
            filtered.groupby("uf", as_index=False)["nota_media_geral"]
            .mean()
            .sort_values("nota_media_geral", ascending=False)
            .head(10)
        )
        fig_bar = px.bar(
            uf_media,
            x="uf",
            y="nota_media_geral",
            color="nota_media_geral",
            title="UFs com melhor média",
            labels={"uf": "UF", "nota_media_geral": "Média"},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("👥 Distribuição por sexo")
        sexo_counts = filtered["sexo"].value_counts().reset_index()
        sexo_counts.columns = ["sexo", "quantidade"]
        fig_pie = px.pie(
            sexo_counts,
            names="sexo",
            values="quantidade",
            title="Participantes por sexo",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("📋 Dados filtrados")
    st.dataframe(filtered.head(2000), use_container_width=True)

    csv_export = filtered.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="Baixar CSV filtrado",
        data=csv_export,
        file_name="enem_dashboard_filtrado.csv",
        mime="text/csv",
    )

    st.subheader("🗂️ Arquivos detectados")
    arquivos_info = []
    for nome, df in datasets.items():
        arquivos_info.append({
            "Arquivo": nome,
            "Linhas": len(df),
            "Colunas": len(df.columns),
        })
    st.dataframe(pd.DataFrame(arquivos_info), use_container_width=True)


if __name__ == "__main__":
    main()
