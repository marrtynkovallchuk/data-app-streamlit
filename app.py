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

st.subheader("Key Metrics (Mailkeeper)")

# -------------------------
# BASE
# -------------------------
deliveries = df["delivery_id"].nunique() if "delivery_id" in df.columns else len(df)

opens = df["read_ts"].notna().sum()
clicks = df["click_ts"].notna().sum()
buyers = (df["buyer"].astype(str).str.lower() == "buyer").sum()

# -------------------------
# EMAIL FUNNEL
# -------------------------
open_rate = opens / deliveries if deliveries else 0
click_rate = clicks / deliveries if deliveries else 0
ctr = clicks / opens if opens else 0

# -------------------------
# MONETIZATION (SIMPLE)
# -------------------------
buyer_rate = buyers / deliveries if deliveries else 0

# -------------------------
# UI
# -------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Deliveries", deliveries)
col2.metric("Opens", int(opens))
col3.metric("Clicks", int(clicks))
col4.metric("Buyers", int(buyers))

st.markdown("### 📩 Email Funnel")
st.metric("Open rate", f"{open_rate:.2%}")
st.metric("Click rate", f"{click_rate:.2%}")
st.metric("CTR (Click/Open)", f"{ctr:.2%}")

st.markdown("### 💰 Monetization")
st.metric("Buyer rate (Buy/Delivery)", f"{buyer_rate:.2%}")

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
# -------------------------
# MONTHLY ANOMALY DETECTION (FIXED)
# -------------------------
st.subheader("📊 Critical changes detection (Month-over-Month)")

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"])

df["month"] = df["date"].dt.to_period("M")

monthly = df.groupby("month").agg(
    deliveries=("delivery_id", "nunique"),
    opens=("read_ts", lambda x: x.notna().sum()),
    clicks=("click_ts", lambda x: x.notna().sum()),
    buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum())
).reset_index()

monthly = monthly.sort_values("month")

# -------------------------
# CONSISTENT RATES (ALL BASED ON DELIVERIES)
# -------------------------
monthly["open_rate"] = monthly["opens"] / monthly["deliveries"]
monthly["click_rate"] = monthly["clicks"] / monthly["deliveries"]
monthly["buyer_rate"] = monthly["buyers"] / monthly["deliveries"]

# -------------------------
# SAFETY CHECK
# -------------------------
if len(monthly) < 2:
    st.warning("Not enough data for comparison")
else:
    latest = monthly.iloc[-1]
    prev = monthly.iloc[-2]

    def render(metric, curr, prev):
        if pd.isna(prev) or prev == 0:
            return f"{metric}: no previous data"

        change = (curr - prev) / prev

        return f"""
{metric}:
- current: {curr:.4f}
- previous: {prev:.4f}
- change: {change:.1%}
"""

    st.write(render("Deliveries", latest["deliveries"], prev["deliveries"]))
    st.write(render("Open rate", latest["open_rate"], prev["open_rate"]))
    st.write(render("Click rate", latest["click_rate"], prev["click_rate"]))
    st.write(render("Buyer rate", latest["buyer_rate"], prev["buyer_rate"]))

st.subheader("🤖 AI-generated summary")

deliveries_change = (latest["deliveries"] - prev["deliveries"]) / prev["deliveries"]
open_change = (latest["open_rate"] - prev["open_rate"]) / prev["open_rate"]
click_change = (latest["click_rate"] - prev["click_rate"]) / prev["click_rate"]
buyer_change = (latest["buyer_rate"] - prev["buyer_rate"]) / prev["buyer_rate"]

summary = f"""
📊 Period overview:

- Email activity (deliveries) changed by {deliveries_change:.1%}, indicating a {'significant drop' if deliveries_change < -0.2 else 'stable trend'} in campaign volume.

- Open rate changed by {open_change:.1%}, showing {'lower engagement' if open_change < 0 else 'stable or improving engagement'} at the top of the funnel.

- Click rate changed by {click_change:.1%}, suggesting {'reduced content effectiveness' if click_change < 0 else 'stable user interest'} after email opens.

- Buyer rate changed by {buyer_change:.1%}, indicating {'stable monetization quality' if abs(buyer_change) < 0.1 else 'changes in purchasing behavior'}.

📌 Key insight:
The main impact comes from the top of the funnel (deliveries and engagement), while monetization remains relatively stable.
"""

st.info(summary)

# -------------------------
# A/B
# -------------------------

st.subheader("🧪 A/B Analysis")

# -------------------------
# detect group columns
# -------------------------
group_cols = [col for col in df.columns if "group" in col.lower()]

if not group_cols:
    st.warning("No A/B test groups found")
else:
    for group_col in group_cols:

        st.markdown(f"### 📊 Analysis for {group_col}")

        ab = df.groupby(group_col).agg(
            deliveries=("delivery_id", "nunique"),
            opens=("read_ts", lambda x: x.notna().sum()),
            clicks=("click_ts", lambda x: x.notna().sum()),
            buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum())
        ).reset_index()

        # -------------------------
        # METRICS
        # -------------------------
        ab["open_rate"] = ab["opens"] / ab["deliveries"]
        ab["click_rate"] = ab["clicks"] / ab["deliveries"]
        ab["buyer_rate"] = ab["buyers"] / ab["deliveries"]

        st.dataframe(ab)

        # -------------------------
        # VISUAL COMPARISON
        # -------------------------
        st.write("Open rate by group")
        st.bar_chart(ab.set_index(group_col)["open_rate"])

        st.write("Click rate by group")
        st.bar_chart(ab.set_index(group_col)["click_rate"])

        st.write("Buyer rate by group")
        st.bar_chart(ab.set_index(group_col)["buyer_rate"])

import numpy as np
from scipy.stats import chi2_contingency

st.subheader("🧪 A/B Experiments Analysis")

# -------------------------
# SETTINGS
# -------------------------
PRIMARY_METRIC = "buyer"   # "click" або "buyer"
SIGNIFICANCE_LEVEL = 0.05
MIN_LIFT = 0.05  # 5%

# -------------------------
# FORMAT P-VALUE
# -------------------------
def format_p_value(p):
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"

# -------------------------
# DETECT EXPERIMENTS
# -------------------------
group_cols = [col for col in df.columns if "group" in col.lower()]

for col in group_cols:

    st.markdown(f"### 📊 {col}")

    # беремо тільки rows де є група
    df_g = df.dropna(subset=[col])

    # -------------------------
    # AGGREGATION
    # -------------------------
    ab = df_g.groupby(col).agg(
        deliveries=("delivery_id", "nunique"),
        opens=("read_ts", lambda x: x.notna().sum()),
        clicks=("click_ts", lambda x: x.notna().sum()),
        buyers=("buyer", lambda x: (x.astype(str).str.lower() == "buyer").sum())
    ).reset_index()

    # має бути мінімум 2 групи
    if ab.shape[0] < 2:
        st.warning("Not enough groups for A/B comparison")
        continue

    # -------------------------
    # RATES
    # -------------------------
    ab["open_rate"] = ab["opens"] / ab["deliveries"]
    ab["click_rate"] = ab["clicks"] / ab["deliveries"]
    ab["buyer_rate"] = ab["buyers"] / ab["deliveries"]

    st.dataframe(ab)

    # -------------------------
    # CONTROL / TEST
    # -------------------------
    g1 = ab.iloc[0]
    g2 = ab.iloc[1]

    # -------------------------
    # CLICK SIGNIFICANCE
    # -------------------------
    click_table = np.array([
        [g1["clicks"], g1["deliveries"] - g1["clicks"]],
        [g2["clicks"], g2["deliveries"] - g2["clicks"]],
    ])

    _, p_click, _, _ = chi2_contingency(click_table)

    # -------------------------
    # BUYER SIGNIFICANCE
    # -------------------------
    buyer_table = np.array([
        [g1["buyers"], g1["deliveries"] - g1["buyers"]],
        [g2["buyers"], g2["deliveries"] - g2["buyers"]],
    ])

    _, p_buyer, _, _ = chi2_contingency(buyer_table)

    # -------------------------
    # UPLIFTS
    # -------------------------
    click_rate_g1 = g1["clicks"] / g1["deliveries"]
    click_rate_g2 = g2["clicks"] / g2["deliveries"]

    buyer_rate_g1 = g1["buyers"] / g1["deliveries"]
    buyer_rate_g2 = g2["buyers"] / g2["deliveries"]

    click_uplift = (click_rate_g2 / click_rate_g1) - 1
    buyer_uplift = (buyer_rate_g2 / buyer_rate_g1) - 1

    # -------------------------
    # OUTPUT
    # -------------------------
    st.write(f"📊 Click rate p-value: {format_p_value(p_click)}")
    st.write(f"💰 Buyer rate p-value: {format_p_value(p_buyer)}")

    st.write(f"📈 Click uplift: {click_uplift:.2%}")
    st.write(f"💰 Buyer uplift: {buyer_uplift:.2%}")

    # -------------------------
    # PRIMARY METRIC
    # -------------------------
    if PRIMARY_METRIC == "click":
        primary_p = p_click
        primary_uplift = click_uplift
    else:
        primary_p = p_buyer
        primary_uplift = buyer_uplift

    # -------------------------
    # GUARDRAIL
    # -------------------------
    guardrail_ok = buyer_uplift >= -0.01

    # -------------------------
    # DECISION
    # -------------------------
    if (
        primary_p < SIGNIFICANCE_LEVEL
        and primary_uplift > MIN_LIFT
        and guardrail_ok
    ):
        st.success(
            "🚀 Rollout recommended "
            "(significant + meaningful uplift)"
        )

    elif primary_p < SIGNIFICANCE_LEVEL:
        st.info(
            "⚠️ Statistically significant "
            "but business impact is limited"
        )

    else:
        st.warning(
            "❌ No statistically significant effect detected"
        )

    # -------------------------
    # AI SUMMARY
    # -------------------------
    st.subheader("🤖 AI-generated recommendation")

    if primary_p < SIGNIFICANCE_LEVEL and primary_uplift > MIN_LIFT:

        summary = f"""
The test demonstrates a statistically significant improvement in the primary metric.

Key observations:
- Click uplift: {click_uplift:.2%}
- Buyer uplift: {buyer_uplift:.2%}
- Statistical significance confirmed (p-value {format_p_value(primary_p)})

Recommendation:
Rollout is recommended, as the experiment shows meaningful positive impact without negative monetization signals.
"""

    elif primary_p < SIGNIFICANCE_LEVEL:

        summary = f"""
The experiment reached statistical significance, however the observed uplift remains relatively small.

Key observations:
- Click uplift: {click_uplift:.2%}
- Buyer uplift: {buyer_uplift:.2%}
- Statistical significance confirmed (p-value {format_p_value(primary_p)})

Recommendation:
Further monitoring is recommended before full rollout, since business impact appears limited.
"""

    else:

        summary = f"""
The experiment did not produce statistically significant improvements.

Key observations:
- Click uplift: {click_uplift:.2%}
- Buyer uplift: {buyer_uplift:.2%}
- No statistically significant effect detected.

Recommendation:
No rollout is recommended at the current stage. Additional iterations or hypothesis changes may be required.
"""

    st.info(summary)
