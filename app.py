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

    # 🔍 basic info
    st.subheader("Dataset Info")
    st.write("Rows:", df.shape[0])
    st.write("Columns:", df.shape[1])

    st.subheader("Column names")
    st.write(df.columns.tolist())

    # 👀 preview
    st.subheader("Preview")
    st.dataframe(df.head())

st.subheader("📊 Key Metrics")

if "buyer" in df.columns:

    total_users = len(df)

    # 🧠 приводимо buyer до 0/1
    if df["buyer"].dtype == "O":
        buyers = (df["buyer"].astype(str).str.lower().isin(["1", "true", "yes", "y"])).sum()
    else:
        buyers = df["buyer"].fillna(0).astype(int).sum()

    conversion_rate = buyers / total_users if total_users > 0 else 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Total users", total_users)
    col2.metric("Buyers", int(buyers))
    col3.metric("Conversion rate", f"{conversion_rate:.2%}")

if "date" in df.columns:
    st.subheader("📈 Daily volume")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    daily = df.groupby("date").size()

    st.line_chart(daily)

st.subheader("🧪 A/B Overview")

group_cols = [col for col in df.columns if "Group" in col or "group" in col]

if group_cols:
    for col in group_cols:
        st.write(f"Distribution for {col}")
        st.bar_chart(df[col].value_counts())
