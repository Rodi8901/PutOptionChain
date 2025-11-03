import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# yoptions importieren
import yoptions as yo  # Bibliothek, die Option-Greeks (inkl. Delta) via Yahoo Finance liefert :contentReference[oaicite:1]{index=1}

st.set_page_config(page_title="Optionsanalyse (mit Delta)", layout="wide")
st.title("📊 Aktien- & Optionsanalyse Dashboard")

ticker_symbol = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):", "INTC").upper()
fee_per_trade = st.number_input("Gebühr pro Handel ($):", min_value=0.0, value=3.5, step=0.5)

if ticker_symbol:
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info
        current_price = stock_info.get("currentPrice", None)

        st.subheader("Optionsdaten")

        if current_price:
            st.markdown(f"**Basiswert:** {ticker_symbol} | **Aktueller Kurs:** {current_price:.2f} USD")

        expirations = ticker.options
        if not expirations:
            st.warning("Keine Optionsdaten für diesen Ticker gefunden.")
        else:
            exp_date = st.selectbox("Bitte ein Ablaufdatum wählen:", expirations)
            opt_chain = ticker.option_chain(exp_date)

            puts = opt_chain.puts.copy()

            cols_to_drop = ["change", "percentChange", "contractSize", "currency", "lastTradeDate"]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            # Falls bid fehlt, fallback auf lastPrice
            puts["bid"] = puts["bid"].fillna(puts["lastPrice"])

            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()
            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Prämie ($)"] = puts["bid"] * 100
            puts["Nettoprämie ($)"] = puts["Prämie ($)"] - fee_per_trade
            puts["Rendite (%)"] = (puts["Nettoprämie ($)"] / (puts["strike"] * 100 - puts["Prämie ($)"])) * 100
            puts["Jahresrendite (%)"] = (puts["Rendite (%)"] / puts["Haltedauer (Tage)"]) * 365
            puts["Sicherheitspolster (%)"] = ((current_price - puts["strike"]) / current_price) * 100

            # --- Delta mit yoptions versuchen zu holen ---
            try:
                chain_greeks = yo.get_chain_greeks(stock_ticker=ticker_symbol,
                                                   dividend_yield=stock_info.get("dividendYield", 0.0),
                                                   option_type='p',  # „p“ für Puts
                                                   expiration=exp_date)
                # Normalerweise liefert chain_greeks ein DataFrame mit Spalte 'Delta'
                greeks_df = chain_greeks[['Strike', 'Delta']].rename(columns={'Strike':'strike', 'Delta':'Delta'})
                greeks_df['strike'] = pd.to_numeric(greeks_df['strike'], errors='coerce')
                greeks_df['Delta']  = pd.to_numeric(greeks_df['Delta'], errors='coerce')

                # Merge greeks in puts
                puts = puts.merge(greeks_df, how='left', on='strike')
            except Exception as e_g:
                st.warning(f"Delta-Werte konnten nicht geladen werden: {e_g}")
                puts['Delta'] = None  # leere Spalte falls Fehler

            # Typen & Rundung
            for col in puts.columns:
                puts[col] = pd.to_numeric(puts[col], errors='ignore')
            numeric_cols = puts.select_dtypes(include=['float', 'int']).columns
            puts[numeric_cols] = puts[numeric_cols].apply(pd.to_numeric, errors='coerce').round(2)

            # Stil-Hervorhebung
            def highlight_and_bold(row):
                if row["strike"] > current_price:
                    bg = "#ffe5e5"
                else:
                    bg = "#e5ffe5"
                font_weight = "bold" if row.get("Jahresrendite (%)", 0) > 10 else "normal"
                return [f"background-color: {bg}; font-weight: {font_weight}"] * len(row)

            puts = puts.sort_values(by="Jahresrendite (%)", ascending=False)
            styled_df = puts.style.apply(highlight_and_bold, axis=1).format(precision=2)

            st.subheader(f"📉 Put-Optionen mit Delta ({exp_date})")
            st.dataframe(styled_df, use_container_width=True)
            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite**")

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
