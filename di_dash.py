import datetime as dt

import pandas as pd
import plotly.graph_objs as go
import pyield as yd
import streamlit as st
from zoneinfo import ZoneInfo

# Constantes
DATE_FORMAT = "%d/%m/%Y"
GRAPH_HEIGHT = 300
BZ_TIMEZONE = ZoneInfo("America/Sao_Paulo")
REALTIME_UPDATE_INTERVAL = "10s"
REALTIME_START_TIME = dt.time(9, 15)
PYIELD_DATA_URL = "https://raw.githubusercontent.com/crdcj/pyield-data/main/"
ANBIMA_RATES_URL = f"{PYIELD_DATA_URL}anbima_rates.csv.gz"

# Streamlit app
st.set_page_config(layout="wide", page_title="Painel DI")

st.markdown(
    """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    margin-top: 1rem;
}
.css-1d391kg {
    margin-bottom: 0 !important;
}
.css-1qpcgxx.e1tzin5v0 {
    margin-top: 0 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Painel Futuro de DI")


def format_di_dataframe(df, pre_maturities):
    """Rename columns of DI rate DataFrame"""
    if "SettlementRate" in df.columns:
        df.rename(columns={"SettlementRate": "DIRate"}, inplace=True)
    elif "CurrentRate" in df.columns:
        df.rename(columns={"CurrentRate": "DIRate"}, inplace=True)
    else:
        raise ValueError("DataFrame does not have a column with DI rates")

    df["ExpirationDate"] = df["ExpirationDate"].apply(lambda x: x.replace(day=1))
    df["ExpirationDate"] = df["ExpirationDate"].dt.date

    df.query("ExpirationDate in @pre_maturities", inplace=True)
    return df


def calculate_variation(df_final, df_initial):
    """Calculate the variation in bps between two DataFrames"""
    df = pd.merge(
        df_final,
        df_initial,
        on="ExpirationDate",
        suffixes=("Final", "Initial"),
    )

    df["Variation"] = (df["DIRateFinal"] - df["DIRateInitial"]) * 10_000

    return df


# Funções de Plotagem
def plot_rate_variation(df_var):
    """Gera o gráfico de barras para variação das taxas."""
    fig_bar = go.Figure()
    fig_bar.add_trace(
        go.Bar(
            x=df_var["ExpirationDate"],
            y=df_var["Variation"],
            name="Variação (bps)",
            # marker_color="gray",
        )
    )
    fig_bar.update_layout(
        title="Variação das Taxas",
        xaxis_title="Data de Expiração",
        yaxis_title="Variação (bps)",
        height=GRAPH_HEIGHT,
        margin=dict(l=10, r=10, t=30, b=0),
        xaxis=dict(showgrid=True, tickformat="%Y", dtick="M12"),
    )
    return fig_bar


def plot_interest_curve(df_start, df_final, start_date, final_date):
    """Gera o gráfico de linha para curva de juros."""
    fig_line = go.Figure()
    fig_line.add_trace(
        go.Scatter(
            x=df_start["ExpirationDate"],
            y=df_start["DIRate"] * 100,
            mode="lines",
            name=f"Curva em {start_date.strftime(DATE_FORMAT)}",
            line=dict(color="gray", dash="dash"),
        )
    )
    fig_line.add_trace(
        go.Scatter(
            x=df_final["ExpirationDate"],
            y=df_final["DIRate"] * 100,
            mode="lines",
            name=f"Curva em {final_date.strftime(DATE_FORMAT)}",
            # line=dict(color="gray"),
        )
    )
    fig_line.update_layout(
        title="Curva de Juros",
        xaxis_title="Data de Expiração",
        yaxis_title="Taxa de Juros (%)",
        height=GRAPH_HEIGHT,
        margin=dict(l=10, r=10, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
        xaxis=dict(showgrid=True, tickformat="%Y", dtick="M12"),
    )
    return fig_line


def plot_graphs():
    # Atualize o DI da data final apenas quando a data final for hoje
    df_final = yd.futures(contract_code="DI1", reference_date=final_date)
    df_final = format_di_dataframe(df_final, pre_maturities)

    df_var = calculate_variation(df_final, df_start)

    fig_bar = plot_rate_variation(df_var)
    fig_line = plot_interest_curve(df_start, df_final, start_date, final_date)
    # Exibir os gráficos no Streamlit
    st.plotly_chart(fig_bar, use_container_width=True)
    st.plotly_chart(fig_line, use_container_width=True)


@st.cache_data(ttl=28800)  # 8 horas de cache
def load_anbima_rates() -> pd.DataFrame:
    df = pd.read_csv(ANBIMA_RATES_URL, parse_dates=["ReferenceDate", "MaturityDate"])
    # Convert columns to datetime.date
    df["ReferenceDate"] = df["ReferenceDate"].dt.date
    df["MaturityDate"] = df["MaturityDate"].dt.date
    return df


# Ajuste o horário para o fuso horário do Brasil
bz_now = dt.datetime.now(BZ_TIMEZONE)
bz_today = bz_now.date()
last_bday = yd.bday.offset(bz_today, 0, roll="backward")

if bz_now.time() < REALTIME_START_TIME:
    default_final_date = yd.bday.offset(last_bday, -1)
else:
    default_final_date = last_bday

default_start_date = yd.bday.offset(default_final_date, -1)

# Inputs para selecionar as datas inicial e final
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    start_date = st.date_input("Selecione a data inicial", value=default_start_date)

with col2:
    final_date = st.date_input("Selecione a data final", value=default_final_date)

num_bdays = yd.bday.count(start_date, final_date)
with col3:
    # Mostrar o número de dias úteis entre as datas selecionadas
    st.metric("Número de dias úteis entre as datas", value=f"{num_bdays}")

# Get NTN-F and LTN maturities
if final_date == bz_today:
    # If date1 is today, we need to get the Anbima data from previous business day
    anbima_date = yd.bday.offset(bz_today, -1)
else:
    anbima_date = final_date

pre_rates = load_anbima_rates().query("ReferenceDate == @anbima_date").copy()
pre_rates.query("BondType in ['LTN', 'NTN-F']", inplace=True)
pre_maturities = pre_rates["MaturityDate"]

df_start = yd.futures(contract_code="DI1", reference_date=start_date)
df_start = format_di_dataframe(df_start, pre_maturities)

df_final = yd.futures(contract_code="DI1", reference_date=final_date)
has_realtime_data = "SettlementRate" not in df_final.columns

# Condicional para atualização periódica dos gráficos
if final_date == bz_today and has_realtime_data:

    @st.fragment(run_every=REALTIME_UPDATE_INTERVAL)
    def periodic_plotter():
        plot_graphs()

    periodic_plotter()
else:
    plot_graphs()

st.markdown(
    """    
    <p style='font-size:10px;'>
    Nota: Dados filtrados para os vértices de emissão de LTN e NTN-F.
    </p>
    """,
    unsafe_allow_html=True,
)
