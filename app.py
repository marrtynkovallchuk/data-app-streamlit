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
    
# Moninoring
    
    st.header("📊 Monitoring")

df["date"] = pd.to_datetime(df["date"], errors="coerce")

# -------------------------
# KPI BLOCK
# -------------------------
st.subheader("Key Metrics")

total_users = len(df)

buyers = (df["buyer"].astype(str).str.lower() == "buyer").sum()

open_rate = df["read_ts"].notna().mean()
click_rate = df["click_ts"].notna().mean()

conversion_rate = buyers / total_users if total_users > 0 else 0

col1, col2, col3, col4 = st.columns(4)

col1.metric("Users", total_users)
col2.metric("Buyers", int(buyers))
col3.metric("Open rate", f"{open_rate:.2%}")
col4.metric("Click rate", f"{click_rate:.2%}")

# -------------------------
# DAILY TRENDS
# -------------------------
st.subheader("📈 Trends over time")

daily = df.groupby("date").agg(
    users=("user_id", "count"),
    buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum()),
).reset_index()

daily["buyer_rate"] = daily["buyers"] / daily["users"]

# 📊 1. volume (users)
st.write("Users over time")
st.line_chart(daily.set_index("date")["users"])

# 📊 2. rate
st.write("Buyer rate over time")
st.line_chart(daily.set_index("date")["buyer_rate"])

# -------------------------
# SIMPLE ANOMALIES
# -------------------------
st.subheader("⚠️ Anomalies")

daily["ma7"] = daily["buyer_rate"].rolling(7).mean()
daily["anomaly"] = daily["buyer_rate"] < daily["ma7"] * 0.9

st.dataframe(daily[daily["anomaly"] == True])
