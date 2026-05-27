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

    # 📊 debug - optional but very useful
    st.subheader("Data types")
    st.write(df.dtypes)

    # 📈 simple visualization (if date exists)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        chart_data = df.groupby("date").size()

        st.subheader("Records over time")
        st.line_chart(chart_data)

else:
    st.info("Upload a CSV file to start analysis 👆")
