import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Optionsanalyse", layout="wide")
st.title("📊 Aktien- & Optionsanalyse Dashboard")

# Eingabefelder
ticker_symbol = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):", "INTC")
fee_per_trade = st.number_input("Gebühr pro Handel ($):", min_value=0.0, value=3.5, step=0.5)

if ticker_symbol:
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info
        current_price = stock_info.get("currentPrice", None)

        st.subheader("Optionsdaten")

        if current_price:
            st.markdown(f"**Basiswert:** {ticker_symbol.upper()} | **Aktueller Kurs:** {current_price:.2f} USD")

        # Ablaufdaten laden
        expirations = ticker.options
        if not expirations:
            st.warning("Keine Optionsdaten für diesen Ticker gefunden.")
        else:
            exp_date = st.selectbox("Bitte ein Ablaufdatum wählen:", expirations)
            opt_chain = ticker.option_chain(exp_date)

            puts = opt_chain.puts.copy()

            # --- Unnötige Spalten entfernen ---
            cols_to_drop = ["change", "percentChange", "contractSize", "currency", "lastTradeDate"]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            # --- Neue Berechnungen ---
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()

            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Nettoprämie ($)"] = (puts["lastPrice"] * 100) - fee_per_trade
            puts["Rendite (%)"] = (puts["Nettoprämie ($)"] / (puts["strike"] * 100 - puts["lastPrice"] * 100)) * 100
            puts["Jahresrendite (%)"] = (puts["Rendite (%)"] / puts["Haltedauer (Tage)"]) * 365
            puts["Sicherheitspolster (%)"] = ((current_price - puts["strike"]) / current_price) * 100


import math
from scipy.stats import norm

# --- Zusätzliche Delta-Berechnung ---
r = 0.045  # risikofreier US-Zins (4,5 %), kannst du dynamisch machen falls gewünscht

def calc_put_delta(S, K, T, sigma, r):
    try:
        if T <= 0 or sigma <= 0:
            return None
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        delta = norm.cdf(d1) - 1  # Put-Delta
        return round(delta, 3)
    except Exception:
        return None

puts["Delta"] = puts.apply(
    lambda row: calc_put_delta(
        current_price,
        row["strike"],
        max(row["Haltedauer (Tage)"], 1) / 365,
        row.get("impliedVolatility", 0.0),
        r,
    ),
    axis=1
)



            
            # --- Datentypen korrigieren & runden ---
            for col in puts.columns:
                puts[col] = pd.to_numeric(puts[col], errors="ignore")

            numeric_cols = puts.select_dtypes(include=['float', 'int']).columns
            puts[numeric_cols] = puts[numeric_cols].apply(pd.to_numeric, errors='coerce').round(2)

            # --- Farb- und Schrift-Hervorhebung ---
            def highlight_and_bold(row):
                styles = []
                if row["strike"] > current_price:
                    bg = "#ffe5e5"  # im Geld
                else:
                    bg = "#e5ffe5"  # aus dem Geld

                # Fett bei Jahresrendite > 10%
                font_weight = "bold" if row.get("Jahresrendite (%)", 0) > 10 else "normal"
                styles = [f"background-color: {bg}; font-weight: {font_weight}"] * len(row)
                return styles

            # Sortieren nach Jahresrendite (höchste zuerst)
            puts = puts.sort_values(by="Jahresrendite (%)", ascending=False)

            styled_df = puts.style.apply(highlight_and_bold, axis=1).format(precision=2)

            st.subheader(f"📉 Put-Optionen ({exp_date})")
            st.dataframe(styled_df, use_container_width=True)

            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite**")

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
