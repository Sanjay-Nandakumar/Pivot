# CPR Option Sale Price Simulator

A manual, deployable Streamlit implementation of the uploaded Pine Script's price simulation formulas, with optional CSV-based historical win-rate evaluation.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Upload `app.py`, `engine.py`, and `requirements.txt` to a GitHub repository (at the repository root).
2. Open https://share.streamlit.io/ and choose **Create app**, selecting your repository, branch, and `app.py`.
3. Deploy and bookmark the resulting URL. Use the Streamlit access controls available to your account if you need privacy.

## Inputs

- **Daily**: use the most recently *completed* regular session's high, low, close. Predict the next session's 09:18 candle **close**.
- **Intraday**: use completed high, low, close for the selected window. Predict the close of the first 3-minute candle immediately after the window.
- You must supply reference HLC manually; this app does not fetch market prices.
- **Manual strike step** is recommended for fixed-strike instruments. Auto matches the uploaded script's price-based interval heuristic.

## CSV backtest

Upload a CSV with `datetime,open,high,low,close` columns, with **3-minute candle opening timestamps in IST**. Include complete NSE sessions from 09:15 through the 15:27 opening candle for daily tests. The test uses the actual first post-window 3-minute close as trigger, and settles at the **following trading session**: at its final close for daily, or its corresponding window-end boundary for intraday. The backtest does not measure your manually entered prediction's accuracy. Rows with missing necessary bars are skipped. Holidays and missing sessions are handled by the next available date, but data gaps can lead to skipped trades.

## Important

This is a scenario calculator, not a price forecasting model. Historical win is a strike-boundary classification, **not** option profitability. There is no broker connectivity, authentication, premium modeling, stop loss, or live market feed. The original script's native signals and historical simulator are separate; this app implements the **simulator**, not the entire indicator.
