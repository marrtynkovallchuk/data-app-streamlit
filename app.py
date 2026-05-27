import streamlit as st
import pandas as pd

st.title("📊 Data App (Upload CSV)")

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.success("File uploaded successfully!")

    # 🔍 preview
    st.subheader("Data preview")
    st.dataframe(df.head())

    # 📊 basic info
    st.subheader("Dataset info")
    st.write("Rows:", df.shape[0])
    st.write("Columns:", df.shape[1])

    # 📈 quick example chart (якщо є date)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        chart_data = df.groupby("date").size()
        st.line_chart(chart_data)

else:
    st.info("Please upload a CSV file to start analysis")
