import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Optionsanalyse", layout="wide")
st.title("📊 Aktien- & Optionsanalyse Dashboard")

# Eingabefelder
ticker_symbol = st.text_input("Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):", "INTC")
fee_per_trade = st.number_input("Gebühr pro Handel ($):", min_value=0.0, value=3.5, step=0.5)

# Zustand speichern, um Laufzeit beizubehalten
if "selected_exp_date" not in st.session_state:
    st.session_state.selected_exp_date = None

if ticker_symbol:
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info
        current_price = stock_info.get("currentPrice", None)

        st.subheader("Optionsdaten")

        if current_price:
            # --- Unternehmensdaten ---
            company_name = stock_info.get("longName", ticker_symbol.upper())
            pe_ratio = stock_info.get("trailingPE", None)
            day_change = stock_info.get("regularMarketChangePercent", None)

            # === Earnings Date mit Fallbacks ===
            earnings_date = stock_info.get("earningsDate", None)
            if not earnings_date:
                try:
                    cal = ticker.calendar
                    if "Earnings Date" in cal.index:
                        earnings_date = cal.loc["Earnings Date"].values[0]
                except Exception:
                    earnings_date = None

            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                earnings_date_display = pd.to_datetime(earnings_date[0]).strftime("%Y-%m-%d")
            elif isinstance(earnings_date, pd.Timestamp):
                earnings_date_display = earnings_date.strftime("%Y-%m-%d")
            elif isinstance(earnings_date, (float, int)):
                earnings_date_display = pd.to_datetime(earnings_date, unit='s').strftime("%Y-%m-%d")
            else:
                earnings_date_display = "—"

            # Formatierungen
            pe_display = f"{pe_ratio:.2f}" if pe_ratio else "—"
            day_change_display = f"{day_change:.2f}%" if day_change else "—"
            if day_change and day_change > 0:
                day_change_display = f"🟢 +{day_change_display}"
            elif day_change and day_change < 0:
                day_change_display = f"🔴 {day_change_display}"

            st.markdown(
                f"""
                **Unternehmen:** {company_name}  
                **Basiswert:** {ticker_symbol.upper()} | **Aktueller Kurs:** {current_price:.2f} USD  
                **KGV:** {pe_display} | **Tägliche Veränderung:** {day_change_display} | **Earnings Date:** {earnings_date_display}
                """
            )

        # Ablaufdaten laden
        expirations = ticker.options
        if not expirations:
            st.warning("Keine Optionsdaten für diesen Ticker gefunden.")
        else:
            # Wochen-/Monatsoptionen erkennen
            def classify_option(exp_date):
                d = datetime.strptime(exp_date, "%Y-%m-%d")
                return "📅 Monatsoption" if d.day >= 15 else "🗓️ Wochenoption"

            exp_labels = [f"{exp} ({classify_option(exp)})" for exp in expirations]

            # Vorherige Auswahl beibehalten, falls verfügbar
            default_index = 0
            if st.session_state.selected_exp_date in expirations:
                default_index = expirations.index(st.session_state.selected_exp_date)

            exp_date_label = st.selectbox("Bitte ein Ablaufdatum wählen:", exp_labels, index=default_index)
            exp_date = exp_date_label.split(" ")[0]
            st.session_state.selected_exp_date = exp_date

            # === OptionCharts-Link ===
            optioncharts_url = f"https://optioncharts.io/options/{ticker_symbol.upper()}/option-chain?option_type=put&expiration_dates={exp_date}:m&view=list&strike_range=all"
            st.markdown(
                f"🔗 **Direkter Link zur Option Chain:** [OptionCharts.io für {ticker_symbol.upper()} – {exp_date}]({optioncharts_url})",
                unsafe_allow_html=True
            )

            opt_chain = ticker.option_chain(exp_date)
            puts = opt_chain.puts.copy()

            # --- Unnötige Spalten entfernen ---
            cols_to_drop = ["change", "percentChange", "contractSize", "currency", "lastTradeDate"]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            # --- Fallback falls kein Bid ---
            puts["bid"] = puts["bid"].fillna(puts["lastPrice"])

            # --- Neue Berechnungen ---
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()
            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Prämie ($)"] = puts["bid"] * 100
            puts["Nettoprämie ($)"] = puts["Prämie ($)"] - fee_per_trade
            puts["Rendite (%)"] = (puts["Nettoprämie ($)"] / (puts["strike"] * 100 - puts["Prämie ($)"])) * 100
            puts["Jahresrendite (%)"] = (puts["Rendite (%)"] / puts["Haltedauer (Tage)"]) * 365
            puts["Sicherheitspolster (%)"] = ((current_price - puts["strike"]) / current_price) * 100

            # --- Runden ---
            numeric_cols = puts.select_dtypes(include=["float", "int"]).columns
            puts[numeric_cols] = puts[numeric_cols].round(2)

            # --- Styling ---
            def highlight_and_style(row):
                bg = "#ffe5e5" if row["strike"] > current_price else "#e5ffe5"
                styles = []
                for col in puts.columns:
                    base = f"background-color:{bg};"
                    if col in ["bid", "Jahresrendite (%)"]:
                        color = "color:#b30000;font-size:1.1em;"
                        if col == "Jahresrendite (%)" and row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base}{color}font-weight:bold;")
                        else:
                            styles.append(f"{base}{color}")
                    else:
                        if row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base}font-weight:bold;")
                        else:
                            styles.append(base)
                return styles

            puts = puts.sort_values(by="strike", ascending=True)
            styled_df = puts.style.apply(highlight_and_style, axis=1).format(precision=2)

            st.subheader(f"📉 Put-Optionen ({exp_date}) – basierend auf BID-Preisen")
            st.dataframe(styled_df, use_container_width=True, height=800)
            st.caption("🟩 Aus dem Geld | 🟥 Im Geld — **fett = >10 % Jahresrendite** | 🔴 Rot = Bid & Rendite")

            # --- TradingView Chart ---
            st.markdown("---")
            st.subheader("📊 TradingView Chart")

            exchange = stock_info.get("exchange", "")
            tv_symbol = ticker_symbol.upper()
            if exchange and exchange.upper() in ["NASDAQ", "NYSE", "AMEX"]:
                tv_full_symbol = f"{exchange.upper()}:{tv_symbol}"
            else:
                tv_full_symbol = tv_symbol

            tradingview_html = f"""
            <div class="tradingview-widget-container" style="width:100%; min-height:900px;">
              <div class="tradingview-widget-container__widget" style="height:100%; width:100%;"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
              {{
              "width": "100%",
              "height": "900",
              "symbol": "{tv_full_symbol}",
              "interval": "D",
              "timezone": "Etc/UTC",
              "theme": "light",
              "style": "1",
              "locale": "en",
              "allow_symbol_change": true
              }}
              </script>
            </div>
            """
            components.html(tradingview_html, height=950)

            # --- Scroll-to-Top Button ---
            scroll_button_html = """
            <button onclick="window.scrollTo({top: 0, behavior: 'smooth'});" 
                    style="
                        position:fixed;
                        bottom:25px;
                        right:25px;
                        background-color:#007bff;
                        color:white;
                        border:none;
                        border-radius:50%;
                        width:55px;
                        height:55px;
                        font-size:24px;
                        cursor:pointer;
                        box-shadow:0 2px 8px rgba(0,0,0,0.3);
                    ">↑</button>
            """
            st.markdown(scroll_button_html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
