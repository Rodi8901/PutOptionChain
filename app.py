import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Optionsanalyse", layout="wide")
st.title("📊 Aktien- & Optionsanalyse Dashboard")

# ------------------------------------------------
# Eingaben
# ------------------------------------------------
ticker_symbol = st.text_input(
    "Bitte Ticker eingeben (z. B. INTC, AAPL, TSLA):",
    "INTC"
)
fee_per_trade = st.number_input(
    "Gebühr pro Handel ($):",
    min_value=0.0,
    value=3.5,
    step=0.5
)

# Zustand speichern
if "selected_exp_date" not in st.session_state:
    st.session_state.selected_exp_date = None

# ------------------------------------------------
# Hauptlogik
# ------------------------------------------------
if ticker_symbol:
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info

        current_price = stock_info.get("currentPrice", None)
        market_cap = stock_info.get("marketCap", None)

        st.subheader("Optionsdaten")

        if current_price:
            company_name = stock_info.get("longName", ticker_symbol.upper())
            pe_ratio = stock_info.get("trailingPE", None)
            day_change = stock_info.get("regularMarketChangePercent", None)
            earnings_date = stock_info.get("earningsDate", None)

            # -----------------------------
            # Formatierungen
            # -----------------------------
            pe_display = f"{pe_ratio:.2f}" if pe_ratio else "—"

            day_change_display = "—"
            if day_change is not None:
                day_change_display = f"{day_change:.2f}%"
                if day_change > 0:
                    day_change_display = f"🟢 +{day_change_display}"
                elif day_change < 0:
                    day_change_display = f"🔴 {day_change_display}"

            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                earnings_date_display = earnings_date[0].strftime("%Y-%m-%d")
            elif isinstance(earnings_date, pd.Timestamp):
                earnings_date_display = earnings_date.strftime("%Y-%m-%d")
            else:
                earnings_date_display = "—"

            def format_market_cap(value):
                if not value:
                    return "—"
                if value >= 1e12:
                    return f"{value / 1e12:.2f} Bio. USD"
                elif value >= 1e9:
                    return f"{value / 1e9:.2f} Mrd. USD"
                else:
                    return f"{value / 1e6:.2f} Mio. USD"

            market_cap_display = format_market_cap(market_cap)

            # -----------------------------
            # Header-Ausgabe
            # -----------------------------
            st.markdown(
                f"""
                **Unternehmen:** {company_name}  
                **Basiswert:** {ticker_symbol.upper()} | **Aktueller Kurs:** {current_price:.2f} USD | **Market Cap:** {market_cap_display}  
                **KGV:** {pe_display} | **Tägliche Veränderung:** {day_change_display} | **Earnings Date:** {earnings_date_display}
                """
            )

        # ------------------------------------------------
        # Optionsdaten
        # ------------------------------------------------
        expirations = ticker.options
        if not expirations:
            st.warning("Keine Optionsdaten für diesen Ticker gefunden.")
        else:
            def classify_option(exp_date):
                d = datetime.strptime(exp_date, "%Y-%m-%d")
                return "📅 Monatsoption" if d.day >= 15 else "🗓️ Wochenoption"

            exp_labels = [f"{exp} ({classify_option(exp)})" for exp in expirations]

            default_index = 0
            if st.session_state.selected_exp_date in expirations:
                default_index = expirations.index(st.session_state.selected_exp_date)

            exp_date_label = st.selectbox(
                "Bitte ein Ablaufdatum wählen:",
                exp_labels,
                index=default_index
            )

            exp_date = exp_date_label.split(" ")[0]
            st.session_state.selected_exp_date = exp_date

            optioncharts_url = (
                f"https://optioncharts.io/options/{ticker_symbol.upper()}"
                f"/option-chain?option_type=put&expiration_dates={exp_date}:m"
                f"&view=list&strike_range=all"
            )

            st.markdown(
                f"🔗 **Direkter Link zur Option Chain:** "
                f"[OptionCharts.io für {ticker_symbol.upper()} – {exp_date}]({optioncharts_url})"
            )

            opt_chain = ticker.option_chain(exp_date)
            puts = opt_chain.puts.copy()

            cols_to_drop = [
                "change", "percentChange", "contractSize",
                "currency", "lastTradeDate"
            ]
            puts = puts.drop(columns=[c for c in cols_to_drop if c in puts.columns])

            puts["bid"] = puts["bid"].fillna(puts["lastPrice"])

            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d")
            today = datetime.now()

            puts["Haltedauer (Tage)"] = (exp_date_obj - today).days
            puts["Prämie ($)"] = puts["bid"] * 100
            puts["Nettoprämie ($)"] = puts["Prämie ($)"] - fee_per_trade
            puts["Rendite (%)"] = (
                puts["Nettoprämie ($)"] /
                (puts["strike"] * 100 - puts["Prämie ($)"])
            ) * 100
            puts["Jahresrendite (%)"] = (
                puts["Rendite (%)"] / puts["Haltedauer (Tage)"]
            ) * 365
            puts["Sicherheitspolster (%)"] = (
                (current_price - puts["strike"]) / current_price
            ) * 100

            for col in puts.columns:
                puts[col] = pd.to_numeric(puts[col], errors="ignore")

            numeric_cols = puts.select_dtypes(include=["float", "int"]).columns
            puts[numeric_cols] = puts[numeric_cols].round(2)

            def highlight_and_style(row):
                bg = "#ffe5e5" if row["strike"] > current_price else "#e5ffe5"
                styles = []
                for col in puts.columns:
                    base = f"background-color: {bg};"
                    if col in ["bid", "Jahresrendite (%)"]:
                        extra = "color:#b30000; font-size:1.05em;"
                        if row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base}{extra} font-weight:bold;")
                        else:
                            styles.append(f"{base}{extra}")
                    else:
                        if row.get("Jahresrendite (%)", 0) > 10:
                            styles.append(f"{base} font-weight:bold;")
                        else:
                            styles.append(base)
                return styles

            puts = puts.sort_values(by="strike")
            styled_df = puts.style.apply(highlight_and_style, axis=1)

            st.subheader(f"📉 Put-Optionen ({exp_date}) – basierend auf BID-Preisen")
            st.dataframe(styled_df, use_container_width=True, height=800)
            st.caption("🟩 OTM | 🟥 ITM — **fett = >10 % Jahresrendite**")

            # ------------------------------------------------
            # TradingView Chart
            # ------------------------------------------------
            st.markdown("---")
            st.subheader("📊 TradingView Chart")

            exchange = stock_info.get("exchange", "")
            tv_symbol = ticker_symbol.upper()
            tv_full_symbol = (
                f"{exchange}:{tv_symbol}"
                if exchange in ["NASDAQ", "NYSE", "AMEX"]
                else tv_symbol
            )

            tradingview_html = f"""
            <div class="tradingview-widget-container" style="width:100%; height:900px;">
              <script src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
              {{
                "autosize": true,
                "symbol": "{tv_full_symbol}",
                "interval": "D",
                "timezone": "Etc/UTC",
                "theme": "light",
                "style": "1",
                "locale": "en"
              }}
              </script>
            </div>
            """

            components.html(tradingview_html, height=950)

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
