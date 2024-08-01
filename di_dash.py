import datetime as dt

import pandas as pd
import plotly.graph_objs as go
import pyield as yd
import streamlit as st


def format_di_dataframe(df, pre_maturities):
    """Rename columns of DI rate DataFrame"""
    if "SettlementRate" in df.columns:
        df.rename(columns={"SettlementRate": "DIRate"}, inplace=True)
    elif "CurrentRate" in df.columns:
        df.rename(columns={"CurrentRate": "DIRate"}, inplace=True)
    else:
        raise ValueError("DataFrame does not have a column with DI rates")

    df["ExpirationDate"] = df["ExpirationDate"].apply(lambda x: x.replace(day=1))

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


# Set the page layout and add custom CSS
st.set_page_config(layout="wide")

# Set the page layout and add custom CSS to remove extra space

st.markdown(
    """
    <style>
    .css-18e3th9 {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    .css-1d391kg {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    .css-1v3fvcr {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
today = dt.date.today()
last_bday = yd.bday.offset(today, 0, roll="backward")

default_start_date = yd.bday.offset(last_bday, -1)
default_final_date = last_bday

st.title("Painel Futuro de DI")

# Inputs para selecionar as datas inicial e final
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Selecione a data inicial", value=default_start_date)

with col2:
    final_date = st.date_input("Selecione a data final", value=default_final_date)

num_bdays = yd.bday.count(start_date, final_date)

# Mostrar o número de dias úteis entre as datas selecionadas
st.write(f"Número de dias úteis entre as datas: {num_bdays} dias")

# Get NTN-F and LTN maturities
if final_date == today:
    # If date1 is today, we need to get the Anbima data from previous business day
    anbima_date = yd.bday.offset(today, -1)
else:
    anbima_date = final_date

ltn_maturities = yd.ltn.anbima_rates(reference_date=anbima_date).index.to_list()
ntnf_maturities = yd.ntnf.anbima_rates(reference_date=anbima_date).index.to_list()
pre_maturities = ltn_maturities + ntnf_maturities

df_final = yd.futures(contract_code="DI1", reference_date=final_date)
df_final = format_di_dataframe(df_final, pre_maturities)

df_start = yd.futures(contract_code="DI1", reference_date=start_date)
df_start = format_di_dataframe(df_start, pre_maturities)

df_var = calculate_variation(df_final, df_start)

# Gráfico de barras para variação
fig_bar = go.Figure()
fig_bar.add_trace(
    go.Bar(
        x=df_var["ExpirationDate"],
        y=df_var["Variation"],
        name="Variação (bps)",
        marker_color="gray",
    )
)
fig_bar.update_layout(
    title="Variação de taxa nos vértices de emissão de LTN e NTN-F",
    xaxis_title="Data de Expiração",
    yaxis_title="Variação (bps)",
    width=800,  # largura do gráfico
    height=300,  # altura do gráfico
    margin=dict(l=20, r=20, t=50, b=20),  # Ajustar margens
)

# Gráfico de linha para curva de juros
fig_line = go.Figure()
fig_line.add_trace(
    go.Scatter(
        x=df_start["ExpirationDate"],
        y=df_start["DIRate"] * 100,
        mode="lines",
        name=f"Curva em {start_date.strftime('%d/%m/%Y')}",
        line=dict(color="black", dash="dash"),
    )
)
fig_line.add_trace(
    go.Scatter(
        x=df_final["ExpirationDate"],
        y=df_final["DIRate"] * 100,
        mode="lines",
        name=f"Curva em {final_date.strftime('%d/%m/%Y')}",
        line=dict(color="black"),
    )
)
fig_line.update_layout(
    title="Curva de Juros nas datas selecionadas",
    xaxis_title="Data de Expiração",
    yaxis_title="Taxa de Juros (%)",
    width=800,  # largura do gráfico
    height=300,  # altura do gráfico
    margin=dict(l=20, r=20, t=50, b=20),  # Ajustar margens
    legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5),
)

# Exibir os gráficos no Streamlit
st.plotly_chart(fig_bar, use_container_width=True)
st.plotly_chart(fig_line, use_container_width=True)
