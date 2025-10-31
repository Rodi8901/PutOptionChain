import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Optionsanalyse", layout="wide")

st.title("📊 Aktien- & Optionsanalyse Dashboard")

ticker_symbol = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):", "INTC")

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

            # Nur Puts anzeigen
            puts = opt_chain.puts.copy()

            # Unerwünschte Spalten entfernen
            cols_to_drop = ["change", "percentChange", "contractSize", "currency"]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            st.subheader(f"📉 Put-Optionen ({exp_date})")
            st.dataframe(puts)

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
