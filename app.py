import streamlit as st
import pandas as pd
import numpy as np
import csv
import plotly.express as px
from scipy.stats import chi2_contingency, norm

st.title("📊 Data App - Email Retention")

SIGNIFICANCE_LEVEL = 0.05
MIN_LIFT = 0.05
ANOMALY_THRESHOLD = 0.20

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is None:
    st.stop()

df = pd.read_csv(
    uploaded_file,
    sep=None,
    engine="python",
    quoting=csv.QUOTE_NONE,
    on_bad_lines="skip",
)
df.columns = df.columns.str.strip().str.lower()

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"])

for col in ["read_ts", "click_ts"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

for col in ["not_free_credits", "total_credits"]:
    df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

df["is_buyer"] = df["buyer"].astype(str).str.lower() == "buyer"
df["is_open"]  = df["read_ts"].notna()  if "read_ts"  in df.columns else False
df["is_click"] = df["click_ts"].notna() if "click_ts" in df.columns else False
# правильна метрика монетизації — платні кредити після кліку з email
df["is_paid"]  = df["not_free_credits"] > 0

st.success("File uploaded successfully!")

# ─────────────────────────────────────────────
# SIDEBAR FILTERS
# ─────────────────────────────────────────────
st.sidebar.header("Filters")

min_d = df["date"].min().date()
max_d = df["date"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_d, max_d),
                                    min_value=min_d, max_value=max_d)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    df = df[(df["date"].dt.date >= date_range[0]) & (df["date"].dt.date <= date_range[1])]

segment = st.sidebar.selectbox("Segment", ["All", "Buyers only", "Non-buyers only"])
if segment == "Buyers only":
    df = df[df["is_buyer"]]
elif segment == "Non-buyers only":
    df = df[~df["is_buyer"]]


# ═══════════════════════════════════════════
# MONITORING
# ═══════════════════════════════════════════
st.header("📊 Monitoring")

deliveries  = df["delivery_id"].nunique() if "delivery_id" in df.columns else len(df)
opens       = int(df["is_open"].sum())
clicks      = int(df["is_click"].sum())
paid        = int(df["is_paid"].sum())
total_creds = df["not_free_credits"].sum()

# послідовна воронка: open/sent, click/open, paid/click
open_rate = opens  / deliveries if deliveries else 0
ctr       = clicks / opens      if opens      else 0
paid_rate = paid   / clicks     if clicks     else 0

st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Deliveries",       f"{deliveries:,}")
col2.metric("Open rate",        f"{open_rate:.2%}", help="Opens / Deliveries")
col3.metric("CTR (Click/Open)", f"{ctr:.2%}",       help="Clicks / Opens")
col4.metric("Paid rate",        f"{paid_rate:.2%}", help="Paid credits > 0 after click / Clicks")

st.metric("Total paid credits", f"{total_creds:,.0f}")

# Funnel
st.subheader("📩 Email Funnel")
funnel = pd.Series(
    {"Delivered": deliveries, "Opened": opens, "Clicked": clicks, "Paid": paid}
)
st.bar_chart(funnel)

# ─────────────────────────────────────────────
# DAILY TRENDS
# ─────────────────────────────────────────────
st.subheader("📈 Trends over time")

daily = (
    df.groupby(df["date"].dt.date)
    .agg(
        deliveries   =("delivery_id",     "nunique"),
        opens        =("is_open",          "sum"),
        clicks       =("is_click",         "sum"),
        paid         =("is_paid",          "sum"),
        paid_credits =("not_free_credits", "sum"),
    )
    .reset_index()
    .rename(columns={"date": "Date"})
)
# конвертуємо в datetime щоб Streamlit показував дні, а не місяці
daily["Date"] = pd.to_datetime(daily["Date"])
daily["open_rate"] = daily["opens"]  / daily["deliveries"].replace(0, np.nan)
daily["ctr"]       = daily["clicks"] / daily["opens"].replace(0, np.nan)
daily["paid_rate"] = daily["paid"]   / daily["clicks"].replace(0, np.nan)

for metric, label in [
    ("open_rate",   "Open Rate"),
    ("ctr",         "CTR (Click/Open)"),
    ("paid_rate",   "Paid Rate"),
    ("paid_credits","Paid Credits"),
]:
    fig = px.line(
        daily, x="Date", y=metric,
        title=label,
        markers=True,
    )
    fig.update_xaxes(
        tickformat="%d.%m",   # показуємо день.місяць
        dtick="D1",           # крок — 1 день
        tickangle=-45,
    )
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────
# DAY-OVER-DAY + ANOMALY DETECTION
# ─────────────────────────────────────────────
st.subheader("📊 Critical Changes (Day-over-Day)")

daily_dod = (
    df.groupby(df["date"].dt.date)
    .agg(
        deliveries =("delivery_id", "nunique"),
        opens      =("is_open",      "sum"),
        clicks     =("is_click",     "sum"),
        paid       =("is_paid",      "sum"),
    )
    .reset_index()
    .sort_values("date")
)
daily_dod["date"] = pd.to_datetime(daily_dod["date"])
daily_dod["open_rate"] = daily_dod["opens"]  / daily_dod["deliveries"].replace(0, np.nan)
daily_dod["ctr"]       = daily_dod["clicks"] / daily_dod["opens"].replace(0, np.nan)
daily_dod["paid_rate"] = daily_dod["paid"]   / daily_dod["clicks"].replace(0, np.nan)

if len(daily_dod) < 2:
    st.warning("Not enough data for day-over-day comparison.")
else:
    curr = daily_dod.iloc[-1]
    prev = daily_dod.iloc[-2]

    st.caption(f"Порiвняння: {curr['date']} vs {prev['date']}")

    for key, label in [("open_rate", "Open Rate"), ("ctr", "CTR"),
                       ("paid_rate", "Paid Rate"), ("deliveries", "Deliveries")]:
        c_val = curr[key]
        p_val = prev[key]
        if pd.notna(p_val) and p_val > 0:
            change = (c_val - p_val) / p_val
            fmt = f"{c_val:.2%}" if key != "deliveries" else f"{int(c_val):,}"
            st.metric(label, fmt, f"{change:+.1%}")
            if abs(change) > ANOMALY_THRESHOLD:
                st.error(f"Critical change in {label}: {change:+.1%}")

# ─────────────────────────────────────────────
# BREAKDOWN: response type + rule
# ─────────────────────────────────────────────
if "response" in df.columns:
    st.subheader("📬 Breakdown by message type")
    resp = (
        df.groupby("response")
        .agg(deliveries=("delivery_id", "nunique"),
             opens=("is_open", "sum"),
             clicks=("is_click", "sum"),
             paid=("is_paid", "sum"),
             paid_credits=("not_free_credits", "sum"))
        .reset_index()
    )
    resp["open_rate"] = resp["opens"]  / resp["deliveries"].replace(0, np.nan)
    resp["ctr"]       = resp["clicks"] / resp["opens"].replace(0, np.nan)
    resp["paid_rate"] = resp["paid"]   / resp["clicks"].replace(0, np.nan)
    st.dataframe(resp)

rule_col = next((c for c in df.columns if c == "rule"), None)
if rule_col:
    st.subheader("📋 Breakdown by Rule")
    rule = (
        df.groupby(rule_col)
        .agg(deliveries=("delivery_id", "nunique"),
             opens=("is_open", "sum"),
             clicks=("is_click", "sum"),
             paid=("is_paid", "sum"))
        .reset_index()
    )
    rule["open_rate"] = rule["opens"]  / rule["deliveries"].replace(0, np.nan)
    rule["ctr"]       = rule["clicks"] / rule["opens"].replace(0, np.nan)
    rule["paid_rate"] = rule["paid"]   / rule["clicks"].replace(0, np.nan)
    st.dataframe(rule)

# ─────────────────────────────────────────────
# SEGMENTATION: buyers vs non-buyers
# ─────────────────────────────────────────────
st.subheader("👥 Buyers vs Non-buyers")

seg = (
    df.groupby("is_buyer")
    .agg(deliveries=("delivery_id", "nunique"),
         opens=("is_open", "sum"),
         clicks=("is_click", "sum"),
         paid=("is_paid", "sum"),
         total_credits=("not_free_credits", "sum"))
    .reset_index()
)
seg["label"]      = seg["is_buyer"].map({True: "Buyers", False: "Non-buyers"})
seg["open_rate"]  = seg["opens"]  / seg["deliveries"].replace(0, np.nan)
seg["ctr"]        = seg["clicks"] / seg["opens"].replace(0, np.nan)
seg["paid_rate"]  = seg["paid"]   / seg["clicks"].replace(0, np.nan)
seg["avg_credits"]= seg["total_credits"] / seg["clicks"].replace(0, np.nan)

st.dataframe(seg[["label","deliveries","open_rate","ctr","paid_rate","avg_credits","total_credits"]])

st.write("Open rate: Buyers vs Non-buyers")
st.bar_chart(seg.set_index("label")["open_rate"])
st.write("CTR: Buyers vs Non-buyers")
st.bar_chart(seg.set_index("label")["ctr"])
st.write("Paid rate: Buyers vs Non-buyers")
st.bar_chart(seg.set_index("label")["paid_rate"])

# ─────────────────────────────────────────────
# AI-GENERATED SUMMARY (rule-based)
# ─────────────────────────────────────────────
st.subheader("🤖 AI-generated summary")

def generate_monitoring_summary(open_rate, ctr, paid_rate, total_creds,
                                 daily_df, anomaly_threshold):
    lines = []

    # open rate
    if open_rate < 0.15:
        lines.append(f"📉 Open rate {open_rate:.1%} — нижче норми. Рекомендується протестувати теми листів та час відправки.")
    elif open_rate > 0.25:
        lines.append(f"✅ Open rate {open_rate:.1%} — вище середнього, хороший рівень залученості.")
    else:
        lines.append(f"📊 Open rate {open_rate:.1%} — в нормальному діапазоні.")

    # ctr
    if ctr < 0.10:
        lines.append(f"⚠️ CTR {ctr:.1%} — основний дроп у воронці між відкриттям і кліком. Пріоритет: покращити CTA та релевантність контенту.")
    elif ctr > 0.20:
        lines.append(f"✅ CTR {ctr:.1%} — контент листів добре конвертує у кліки.")
    else:
        lines.append(f"📊 CTR {ctr:.1%} — є потенціал для покращення через A/B тести CTA.")

    # paid rate
    if paid_rate < 0.15:
        lines.append(f"🔴 Paid rate {paid_rate:.1%} — низька конверсія кліків у витрати кредитів. Варто перевірити релевантність офферу на посадковій сторінці.")
    elif paid_rate > 0.30:
        lines.append(f"💚 Paid rate {paid_rate:.1%} — сильна монетизація після кліку.")
    else:
        lines.append(f"📊 Paid rate {paid_rate:.1%} — помірна конверсія, варто сегментувати відправки на buyers та non-buyers.")

    # DoD anomalies
    if len(daily_df) >= 2:
        curr_m = daily_df.iloc[-1]
        prev_m = daily_df.iloc[-2]
        for key, label in [("open_rate","Open rate"), ("ctr","CTR"), ("paid_rate","Paid rate")]:
            if pd.notna(prev_m[key]) and prev_m[key] > 0:
                change = (curr_m[key] - prev_m[key]) / prev_m[key]
                if change < -anomaly_threshold:
                    lines.append(f"{label} впав на {abs(change):.0%} DoD — критична змiна, потребує аналiзу.")
                elif change > anomaly_threshold:
                    lines.append(f"{label} вирiс на {change:.0%} DoD — позитивна динамiка.")

    lines.append(f"💡 Загальна рекомендація: фокус на сегменті buyers та тестування персоналізованого контенту для підвищення CTR і paid rate.")
    return "\n\n".join(lines)

if st.button("Generate summary"):
    summary = generate_monitoring_summary(
        open_rate, ctr, paid_rate, total_creds, daily_dod, ANOMALY_THRESHOLD
    )
    st.info(summary)


# ═══════════════════════════════════════════
# A/B ANALYSIS
# ═══════════════════════════════════════════
st.header("🧪 A/B Analysis")

group_cols = [c for c in df.columns if "group" in c.lower()]

if not group_cols:
    st.warning("No A/B test groups found in data.")
else:
    selected_group = st.selectbox("Select experiment", group_cols)

    df_g = df.dropna(subset=[selected_group])
    vals = df_g[selected_group].unique()

    # явно знаходимо control і test — без залежності від порядку рядків
    control_val = next((v for v in vals if str(v).lower() == "control"), None)
    test_val    = next((v for v in vals if str(v).lower() == "test"),    None)

    if control_val is None or test_val is None:
        st.warning(f"Не знайдено 'Control'/'Test' у колонці {selected_group}. Знайдено: {list(vals)}")
    else:
        df_ctrl = df_g[df_g[selected_group] == control_val]
        df_test = df_g[df_g[selected_group] == test_val]

        def group_metrics(gdf):
            d     = gdf["delivery_id"].nunique() if "delivery_id" in gdf.columns else len(gdf)
            o     = int(gdf["is_open"].sum())
            c     = int(gdf["is_click"].sum())
            p     = int(gdf["is_paid"].sum())
            creds = gdf["not_free_credits"].sum()
            return dict(
                deliveries=d, opens=o, clicks=c, paid=p, credits=creds,
                open_rate = o / d if d else 0,
                ctr       = c / o if o else 0,
                paid_rate = p / c if c else 0,
                avg_creds = creds / c if c else 0,
            )

        ctrl = group_metrics(df_ctrl)
        test = group_metrics(df_test)

        # Порівняльна таблиця
        st.subheader("Metrics comparison")
        ab_df = pd.DataFrame({
            "Metric":  ["Deliveries", "Open rate", "CTR (Click/Open)",
                        "Paid rate", "Avg paid credits/click"],
            "Control": [ctrl["deliveries"], f"{ctrl['open_rate']:.2%}",
                        f"{ctrl['ctr']:.2%}", f"{ctrl['paid_rate']:.2%}",
                        f"{ctrl['avg_creds']:.1f}"],
            "Test":    [test["deliveries"], f"{test['open_rate']:.2%}",
                        f"{test['ctr']:.2%}", f"{test['paid_rate']:.2%}",
                        f"{test['avg_creds']:.1f}"],
        })
        st.dataframe(ab_df)

        # Visual
        rates = pd.DataFrame({
            "open_rate":  [ctrl["open_rate"],  test["open_rate"]],
            "ctr":        [ctrl["ctr"],         test["ctr"]],
            "paid_rate":  [ctrl["paid_rate"],   test["paid_rate"]],
        }, index=["Control", "Test"])

        st.write("Open rate by group")
        st.bar_chart(rates["open_rate"])
        st.write("CTR by group")
        st.bar_chart(rates["ctr"])
        st.write("Paid rate by group")
        st.bar_chart(rates["paid_rate"])

        # ── Statistical significance ──
        st.subheader("📐 Statistical significance")

        def chi2_with_ci(n1, k1, n2, k2, alpha=0.05):
            p1 = k1 / n1 if n1 else 0
            p2 = k2 / n2 if n2 else 0
            table = np.array([[k1, n1-k1], [k2, n2-k2]])
            if table.min() < 5:
                return p1, p2, None, None, None
            _, p_val, _, _ = chi2_contingency(table)
            se   = np.sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2)
            z    = norm.ppf(1 - alpha/2)
            diff = p2 - p1
            ci   = (diff - z*se, diff + z*se)
            uplift = (p2/p1 - 1) if p1 > 0 else None
            return p1, p2, p_val, uplift, ci

        r_open = chi2_with_ci(ctrl["deliveries"], ctrl["opens"],
                               test["deliveries"], test["opens"])
        r_ctr  = chi2_with_ci(ctrl["opens"],      ctrl["clicks"],
                               test["opens"],      test["clicks"])
        r_paid = chi2_with_ci(ctrl["clicks"],     ctrl["paid"],
                               test["clicks"],     test["paid"])

        def fmt_p(p):
            if p is None: return "N/A (low counts)"
            return f"{p:.4f}"

        def fmt_upl(u):
            return f"{u:+.1%}" if u is not None else "N/A"

        def fmt_ci(ci):
            if ci is None: return "N/A"
            return f"[{ci[0]:+.2%}, {ci[1]:+.2%}]"

        stat_df = pd.DataFrame({
            "Metric":        ["Open rate", "CTR", "Paid rate"],
            "Control":       [f"{r_open[0]:.2%}", f"{r_ctr[0]:.2%}", f"{r_paid[0]:.2%}"],
            "Test":          [f"{r_open[1]:.2%}", f"{r_ctr[1]:.2%}", f"{r_paid[1]:.2%}"],
            "Uplift":        [fmt_upl(r_open[3]), fmt_upl(r_ctr[3]), fmt_upl(r_paid[3])],
            "95% CI (diff)": [fmt_ci(r_open[4]),  fmt_ci(r_ctr[4]),  fmt_ci(r_paid[4])],
            "p-value":       [fmt_p(r_open[2]),   fmt_p(r_ctr[2]),   fmt_p(r_paid[2])],
        })
        st.dataframe(stat_df)

        # ── Decision ──
        st.subheader("Decision")

        primary_sig    = r_paid[2] is not None and r_paid[2] < SIGNIFICANCE_LEVEL
        primary_uplift = r_paid[3] if r_paid[3] is not None else 0
        # guardrail: CTR не повинен впасти більш ніж на 5%
        guardrail_ok   = r_ctr[3] is None or r_ctr[3] >= -0.05

        if primary_sig and primary_uplift > MIN_LIFT and guardrail_ok:
            st.success("🚀 Rollout recommended — significant uplift in paid rate, guardrail passed")
        elif primary_sig and not guardrail_ok:
            st.error("🛑 Guardrail failed — CTR dropped, investigate before rollout")
        elif primary_sig:
            st.info("⚠️ Significant but uplift is below business threshold (5%)")
        else:
            st.warning("❌ No significant effect on paid rate — do not rollout")

        # ── AI recommendation ──
        st.subheader("🤖 AI-generated recommendation")

        def generate_ab_summary(r_open, r_ctr, r_paid, ctrl, test, guardrail_ok,
                                  primary_sig, primary_uplift, min_lift):
            lines = []
            uplift_paid = r_paid[3]
            pval_paid   = r_paid[2]
            uplift_ctr  = r_ctr[3]

            if uplift_paid is not None:
                if uplift_paid > 0.05:
                    lines.append(f"📈 Тест показує +{uplift_paid:.1%} uplift у paid rate — позитивний сигнал для монетизації.")
                elif uplift_paid < -0.05:
                    lines.append(f"📉 Тест показує {uplift_paid:.1%} у paid rate — негативний ефект на монетизацію.")
                else:
                    lines.append(f"➡️ Uplift paid rate {uplift_paid:.1%} — ефект невеликий, нижче бізнес-порогу.")

            if pval_paid is not None:
                if pval_paid < 0.05:
                    lines.append(f"✅ Результат статистично значущий (p={pval_paid:.4f}).")
                else:
                    lines.append(f"❌ Результат не значущий (p={pval_paid:.4f}) — можливо шум або замала вибірка.")
            else:
                lines.append("⚠️ Замало даних для статистичного тесту.")

            if guardrail_ok:
                lines.append("✅ Guardrail (CTR) пройдено — залученість не погіршилась.")
            else:
                lines.append(f"🛑 Guardrail не пройдено — CTR впав на {uplift_ctr:.1%}. Ризиковано для довгострокового retention.")

            if primary_sig and primary_uplift > min_lift and guardrail_ok:
                lines.append("🚀 Рекомендація: впроваджувати. Моніторити paid credits та CTR перші 2 тижні після rollout.")
            elif primary_sig and not guardrail_ok:
                lines.append("⏸️ Рекомендація: не впроваджувати без додаткового аналізу падіння CTR.")
            else:
                lines.append("⏸️ Рекомендація: не впроваджувати. Переглянути гіпотезу або зібрати більше даних.")

            return "\n\n".join(lines)

        if st.button(f"Generate recommendation for {selected_group}"):
            rec = generate_ab_summary(
                r_open, r_ctr, r_paid, ctrl, test,
                guardrail_ok, primary_sig, primary_uplift, MIN_LIFT
            )
            st.info(rec)
