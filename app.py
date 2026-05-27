import streamlit as st
import pandas as pd
import csv

st.title("📊 Data App - CSV Analyzer")

# 📥 Upload file
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:

    # 📌 read CSV (auto-detect separator)
    df = pd.read_csv(
        uploaded_file,
        sep=None,
        engine="python",
        quoting=csv.QUOTE_NONE,
        on_bad_lines="skip"
    )

    st.success("File uploaded successfully!")

    st.header("📊 Monitoring")

df["date"] = pd.to_datetime(df["date"], errors="coerce")

# -------------------------
# KPI
# -------------------------
st.subheader("Key Metrics")

total_users = len(df)
buyers = (df["buyer"].astype(str).str.lower() == "buyer").sum()
buyer_rate = buyers / total_users if total_users > 0 else 0

col1, col2, col3 = st.columns(3)

col1.metric("Users", total_users)
col2.metric("Buyers", int(buyers))
col3.metric("Buyer rate", f"{buyer_rate:.2%}")

# -------------------------
# Daily trends (core)
# -------------------------
st.subheader("📈 Trends over time")

daily = df.groupby("date").agg(
    users=("user_id", "count"),
    buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum())
).reset_index()

daily["buyer_rate"] = daily["buyers"] / daily["users"]

st.line_chart(daily.set_index("date")[["users", "buyer_rate"]])

# -------------------------
# simple anomaly detection
# -------------------------
st.subheader("⚠️ Anomalies")

daily["ma7"] = daily["buyer_rate"].rolling(7).mean()
daily["anomaly"] = daily["buyer_rate"] < daily["ma7"] * 0.9

st.dataframe(daily[daily["anomaly"] == True])
