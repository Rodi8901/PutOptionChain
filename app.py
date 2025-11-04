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

            # --- Fallback falls kein Bid vorhanden ---
            puts["bid"] = puts["bid"].fillna(puts["lastPrice"])

            # --- Neue Berechnungen (auf Basis Bid-Kurs) ---
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()

            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Prämie ($)"] = puts["bid"] * 100
            puts["Nettoprämie ($)"] = puts["Prämie ($)"] - fee_per_trade
            puts["Rendite (%)"] = (puts["Nettoprämie ($)"] / (puts["strike"] * 100 - puts["Prämie ($)"])) * 100
            puts["Jahresrendite (%)"] = (puts["Rendite (%)"] / puts["Haltedauer (Tage)"]) * 365
            puts["Sicherheitspolster (%)"] = ((current_price - puts["strike"]) / current_price) * 100

            # --- Datentypen korrigieren & runden ---
            for col in puts.columns:
                puts[col] = pd.to_numeric(puts[col], errors="ignore")

            numeric_cols = puts.select_dtypes(include=['float', 'int']).columns
            puts[numeric_cols] = puts[numeric_cols].apply(pd.to_numeric, errors='coerce').round(2)

            # --- Farb- und Schrift-Hervorhebung ---
            def highlight_and_bold(row):
                if row["strike"] > current_price:
                    bg = "#ffe5e5"  # im Geld
                else:
                    bg = "#e5ffe5"  # aus dem Geld
                font_weight = "bold" if row.get("Jahresrendite (%)", 0) > 10 else "normal"
                font_bold_cols = ["bid", "Jahresrendite (%)"]
                return [
                    f"background-color: {bg}; font-weight: bold"
                    if col in font_bold_cols else f"background-color: {bg}; font-weight: {font_weight}"
                    for col in row.index
                ]

            # --- Sortieren nach Strike ---
            puts = puts.sort_values(by="strike", ascending=True)

            styled_df = puts.style.apply(highlight_and_bold, axis=1).format(precision=2)

            st.subheader(f"📉 Put-Optionen ({exp_date}) – basierend auf BID-Preisen")
            st.dataframe(styled_df, use_container_width=True, height=700)
            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite**")

            # ------------------------------
            #   STRIKE-ANALYSE MIT MINI-CHART
            # ------------------------------
            st.subheader("🎯 Strike-Analyse über Laufzeiten")
            target_strike = st.number_input("Strike-Wert für Analyse eingeben:", min_value=0.0, step=1.0, value=float(current_price) if current_price else 100.0)

            strike_data = []
            for exp in expirations:
                try:
                    opt_chain = ticker.option_chain(exp)
                    puts_exp = opt_chain.puts
                    puts_exp["bid"] = puts_exp["bid"].fillna(puts_exp["lastPrice"])
                    exp_date_obj = datetime.strptime(exp, "%Y-%m-%d")
                    days = (exp_date_obj - today).days
                    row = puts_exp.loc[puts_exp["strike"] == target_strike]
                    if not row.empty:
                        bid = row["bid"].values[0]
                        volume = row["volume"].values[0]
                        oi = row["openInterest"].values[0]
                        prem = bid * 100
                        rendite = (prem / (target_strike * 100 - prem)) * 100
                        jahresrendite = (rendite / days) * 365 if days > 0 else 0
                        strike_data.append({
                            "Laufzeit": exp,
                            "Bid": bid,
                            "Jahresrendite (%)": jahresrendite,
                            "Volumen": volume,
                            "Open Interest": oi
                        })
                except Exception:
                    continue

            if strike_data:
                df_strike = pd.DataFrame(strike_data)
                df_strike = df_strike.round(2)

                st.write("📅 Renditeübersicht für Strike", target_strike)
                st.dataframe(df_strike.set_index("Laufzeit").T, use_container_width=True)

                # --- Mini Chart unter der Tabelle ---
                st.subheader("📈 Jahresrendite über Laufzeiten")
                st.line_chart(df_strike.set_index("Laufzeit")["Jahresrendite (%)"])

            else:
                st.info("Keine passenden Daten für diesen Strike gefunden.")

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
