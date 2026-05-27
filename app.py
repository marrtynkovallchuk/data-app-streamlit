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

st.subheader("Key Metrics")

# -------------------------
# USER-LEVEL BASE
# -------------------------
user_df = df.copy()

user_df["is_buyer"] = user_df["buyer"].astype(str).str.lower() == "buyer"

user_level = user_df.groupby("user_id").agg(
    buyer=("is_buyer", "max"),
    opened=("read_ts", lambda x: x.notna().any()),
    clicked=("click_ts", lambda x: x.notna().any())
).reset_index()

# -------------------------
# BASE COUNTS
# -------------------------
users = len(user_level)
buyers = user_level["buyer"].sum()
opens = user_level["opened"].sum()
clicks = user_level["clicked"].sum()

# -------------------------
# SAFE METRICS (CONSISTENT)
# -------------------------
open_rate = opens / users if users else 0
click_rate = clicks / users if users else 0

ctr_open = clicks / opens if opens else 0
conversion_rate = buyers / users if users else 0
conv_per_click = buyers / clicks if clicks else 0

# -------------------------
# SANITY CHECK (важливо!)
# -------------------------
st.caption(f"Sanity: opens={opens}, clicks={clicks}, users={users}")

# -------------------------
# UI
# -------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Users", users)
col2.metric("Buyers", int(buyers))
col3.metric("Open rate", f"{open_rate:.2%}")
col4.metric("Click rate", f"{click_rate:.2%}")

col5, col6 = st.columns(2)

col5.metric("CTR (Click/Open)", f"{ctr_open:.2%}")
col6.metric("Conv per click", f"{conv_per_click:.2%}")

st.metric("Conversion rate", f"{conversion_rate:.2%}")

# -------------------------
# 📊 BREAKDOWNS (РОЗРІЗИ)
# -------------------------

st.markdown("### 🧩 Segments breakdown")

# 1. Buyer split
buyer_dist = df["buyer"].astype(str).str.lower().value_counts()
st.write("Buyer distribution")
st.bar_chart(buyer_dist)

# 2. Group breakdown (якщо є)
group_cols = [c for c in df.columns if "group" in c.lower()]

for col in group_cols:
    st.write(f"Distribution: {col}")
    st.bar_chart(df[col].value_counts())

# 3. Response breakdown (якщо є)
if "response" in df.columns:
    st.write("Response type distribution")
    st.bar_chart(df["response"].value_counts())

# -------------------------
# DAILY TRENDS
# -------------------------
st.subheader("📈 Trends over time")

daily = df.groupby("date").agg(
    users=("user_id", "count"),
    buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum()),
    opens=("read_ts", lambda x: x.notna().sum()) if "read_ts" in df.columns else ("user_id", "count"),
    clicks=("click_ts", lambda x: x.notna().sum()) if "click_ts" in df.columns else ("user_id", "count"),
).reset_index()

# rates
daily["buyer_rate"] = daily["buyers"] / daily["users"]
daily["open_rate"] = daily["opens"] / daily["users"]
daily["click_rate"] = daily["clicks"] / daily["opens"].replace(0, 1)
daily["conversion_rate"] = daily["buyers"] / daily["clicks"].replace(0, 1)

# -------------------------
# 📊 1. USERS
# -------------------------
st.write("Users over time")
st.line_chart(daily.set_index("date")["users"])

# -------------------------
# 📊 2. BUYER RATE
# -------------------------
st.write("Buyer rate over time")
st.line_chart(daily.set_index("date")["buyer_rate"])

# -------------------------
# 📊 3. OPEN RATE
# -------------------------
st.write("Open rate over time")
st.line_chart(daily.set_index("date")["open_rate"])

# -------------------------
# 📊 4. CLICK RATE
# -------------------------
st.write("Click rate over time")
st.line_chart(daily.set_index("date")["click_rate"])

# -------------------------
# 📊 5. CONVERSION RATE
# -------------------------
st.write("Conversion rate over time")
st.line_chart(daily.set_index("date")["conversion_rate"])

# -------------------------
# SIMPLE ANOMALIES
# -------------------------
st.subheader("⚠️ Anomalies")

daily["ma7"] = daily["buyer_rate"].rolling(7).mean()
daily["anomaly"] = daily["buyer_rate"] < daily["ma7"] * 0.9

st.dataframe(daily[daily["anomaly"] == True])
