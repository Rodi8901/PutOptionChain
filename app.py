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
                return [f"background-color: {bg}; font-weight: {font_weight}"] * len(row)

            def emphasize_columns(val, col_name):
                if col_name in ["bid", "Jahresrendite (%)"]:
                    return "font-weight: bold"
                return ""

            # --- Sortieren nach Strike (aufsteigend) ---
            puts = puts.sort_values(by="strike", ascending=True)

            styled_df = (
                puts.style
                .apply(highlight_and_bold, axis=1)
                .applymap_index(lambda _: "font-weight: bold;", axis=0)
                .apply(lambda s: [emphasize_columns(v, s.name) for v in s], axis=0)
                .format(precision=2)
            )

            st.subheader(f"📉 Put-Optionen ({exp_date}) – basierend auf BID-Preisen")
            st.dataframe(styled_df, use_container_width=True, height=900)

            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite, sowie BID und Jahresrendite hervorgehoben**")

            # ---------------------------------------------
            # 🔍 Zusatzfunktion: Strike-Analyse über alle Laufzeiten
            # ---------------------------------------------
            st.markdown("---")
            st.subheader("📈 Strike-Vergleich über Laufzeiten")

            strike_input = st.number_input("Strike-Wert für Vergleich eingeben:", min_value=0.0, value=float(puts["strike"].median()), step=1.0)

            summary_data = {"Ablaufdatum": [], "Bid": [], "Jahresrendite (%)": [], "Volumen": [], "Open Interest": []}

            for exp in expirations:
                try:
                    chain = ticker.option_chain(exp).puts
                    chain["bid"] = chain["bid"].fillna(chain["lastPrice"])
                    exp_obj = datetime.strptime(exp, "%Y-%m-%d")
                    days = (exp_obj - today).days

                    # Nächster Strike zur Eingabe finden
                    closest = chain.iloc[(chain["strike"] - strike_input).abs().argsort()[:1]]
                    bid = float(closest["bid"])
                    premium = bid * 100
                    rendite = (premium - fee_per_trade) / (closest["strike"].values[0] * 100 - premium) * 100
                    jahresrendite = (rendite / days) * 365 if days > 0 else None

                    summary_data["Ablaufdatum"].append(exp)
                    summary_data["Bid"].append(round(bid, 2))
                    summary_data["Jahresrendite (%)"].append(round(jahresrendite, 2) if jahresrendite else None)
                    summary_data["Volumen"].append(int(closest["volume"].values[0]))
                    summary_data["Open Interest"].append(int(closest["openInterest"].values[0]))
                except Exception:
                    continue

            summary_df = pd.DataFrame(summary_data).set_index("Ablaufdatum").T

            st.dataframe(summary_df.style.format(precision=2), use_container_width=True)

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
