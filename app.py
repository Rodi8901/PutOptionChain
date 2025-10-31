import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien- & Optionsanalyse", layout="wide")

st.title("📊 Aktien- & Optionsanalyse Dashboard")

# Eingabefeld für Ticker
ticker = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, META)", "INTC").upper()

if ticker:
    try:
        stock = yf.Ticker(ticker)

        # Spaltenlayout
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"📈 Kursentwicklung ({ticker})")
            hist = stock.history(period="6mo")
            if not hist.empty:
                st.line_chart(hist["Close"])
            else:
                st.warning("Keine Kursdaten gefunden.")

        with col2:
            st.subheader("🏦 Quartalsdaten")
            qf = stock.quarterly_financials
            if not qf.empty:
                st.dataframe(qf)
            else:
                st.info("Keine Quartalsdaten verfügbar.")

        st.divider()

        # Optionsdaten
        st.subheader("📅 Optionen")
        expirations = stock.options
        if expirations:
            selected_exp = st.selectbox("Verfall auswählen", expirations)

            if selected_exp:
                try:
                    chain = stock.option_chain(selected_exp)
                    st.markdown(f"### Calls – {selected_exp}")
                    st.dataframe(chain.calls)

                    st.markdown(f"### Puts – {selected_exp}")
                    st.dataframe(chain.puts)
                except Exception as e:
                    st.error(f"Fehler beim Laden der Optionskette: {e}")
        else:
            st.info("Für diesen Ticker wurden keine Optionsdaten gefunden.")

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
