
import pandas as pd
import numpy as np
import csv
import os
from scipy.stats import chi2_contingency, norm
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Email Retention Dashboard", layout="wide")
st.title("📧 Email Retention Dashboard")

SIGNIFICANCE_LEVEL = 0.05
MIN_LIFT           = 0.05   # мінімальний бізнес-ефект
ANOMALY_THRESHOLD  = 0.20   # 20% зміна = критична


# ─────────────────────────────────────────────────────────
# AI SUMMARY  (реальний API-call)
# ─────────────────────────────────────────────────────────
def get_ai_summary(prompt: str) -> str:
    try:
        import anthropic
        api_key = (
            st.secrets.get("ANTHROPIC_API_KEY", None)
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            return (
                "⚠️ ANTHROPIC_API_KEY не задано. "
                "Додай його у .streamlit/secrets.toml або як змінну середовища."
            )
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ Помилка AI: {e}"


# ─────────────────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────────────────
uploaded_file = st.sidebar.file_uploader("📁 Завантажити CSV", type=["csv"])

if uploaded_file is None:
    st.info("Завантаж CSV-файл щоб почати.")
    st.stop()

df_raw = pd.read_csv(
    uploaded_file,
    sep=None,
    engine="python",
    quoting=csv.QUOTE_NONE,
    on_bad_lines="skip",
)

# ─────────────────────────────────────────────────────────
# PREPROCESSING
# ─────────────────────────────────────────────────────────
# нормалізуємо назви колонок до нижнього регістру
df_raw.columns = df_raw.columns.str.strip().str.lower()

df = df_raw.copy()

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"])

for col in ["read_ts", "click_ts", "send_ts", "delivery_ts",
            "confirm_timestamp", "last_answer_timestamp"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

for col in ["not_free_credits", "total_credits"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    else:
        df[col] = 0

# бінарні прапори
df["is_buyer"]  = df["buyer"].astype(str).str.lower() == "buyer"
df["is_open"]   = df["read_ts"].notna()   if "read_ts"   in df.columns else False
df["is_click"]  = df["click_ts"].notna()  if "click_ts"  in df.columns else False
# правильна метрика монетизації — платні кредити витрачені після кліку
df["is_paid"]   = df["not_free_credits"] > 0


# ─────────────────────────────────────────────────────────
# SIDEBAR FILTERS
# ─────────────────────────────────────────────────────────
min_d = df["date"].min().date()
max_d = df["date"].max().date()

date_range = st.sidebar.date_input(
    "📅 Період",
    value=(min_d, max_d),
    min_value=min_d,
    max_value=max_d,
)
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s_date, e_date = date_range
    df = df[(df["date"].dt.date >= s_date) & (df["date"].dt.date <= e_date)]
else:
    s_date, e_date = min_d, max_d

segment_filter = st.sidebar.selectbox(
    "👤 Сегмент",
    ["All", "Buyers only", "Non-buyers only"],
)
if segment_filter == "Buyers only":
    df = df[df["is_buyer"]]
elif segment_filter == "Non-buyers only":
    df = df[~df["is_buyer"]]


# ─────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Моніторинг", "🧪 A/B Аналіз", "👥 Сегменти"])
# ═══════════════════════════════════════════════════════
# TAB 1 — MONITORING
# ═══════════════════════════════════════════════════════
with tab1:

    # ── Топ-метрики ─────────────────────────────────────
    deliveries   = df["delivery_id"].nunique() if "delivery_id" in df.columns else len(df)
    opens        = int(df["is_open"].sum())
    clicks       = int(df["is_click"].sum())
    paid_events  = int(df["is_paid"].sum())
    total_creds  = df["not_free_credits"].sum()

    # Послідовна логіка воронки:
    #   open_rate  = Opens  / Deliveries
    #   ctr        = Clicks / Opens      (click-to-open rate)
    #   paid_rate  = Paid   / Clicks     (конверсія в оплату після кліку)
    open_rate = opens       / deliveries if deliveries else 0
    ctr       = clicks      / opens      if opens      else 0
    paid_rate = paid_events / clicks     if clicks     else 0

    st.subheader("📩 Email Funnel")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Deliveries",          f"{deliveries:,}")
    c2.metric("Open rate",           f"{open_rate:.1%}",
              help="Opens / Deliveries")
    c3.metric("CTR (Click/Open)",    f"{ctr:.1%}",
              help="Clicks / Opens")
    c4.metric("Paid rate",           f"{paid_rate:.1%}",
              help="Клікнувших, хто витратив платні кредити / Clicks")
    c5.metric("Total paid credits",  f"{total_creds:,.0f}")

    # ── Funnel bar chart ────────────────────────────────
    funnel_df = pd.DataFrame({
        "Stage":  ["Delivered", "Opened", "Clicked", "Paid"],
        "Count":  [deliveries, opens, clicks, paid_events],
    })
    fig_funnel = px.bar(
        funnel_df, x="Stage", y="Count",
        title="Email Funnel",
        text_auto=True, color="Stage",
        color_discrete_sequence=px.colors.sequential.Blues_r,
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

    # ── Daily trends ────────────────────────────────────
    st.subheader("📈 Тренди в динаміці")

    daily = (
        df.groupby(df["date"].dt.date)
        .agg(
            deliveries      =("delivery_id",       "nunique"),
            opens           =("is_open",            "sum"),
            clicks          =("is_click",           "sum"),
            paid            =("is_paid",            "sum"),
            paid_credits    =("not_free_credits",   "sum"),
        )
        .reset_index()
    )
    daily.rename(columns={"date": "Date"}, inplace=True)
    daily["open_rate"]   = daily["opens"]  / daily["deliveries"].replace(0, np.nan)
    daily["ctr"]         = daily["clicks"] / daily["opens"].replace(0, np.nan)
    daily["paid_rate"]   = daily["paid"]   / daily["clicks"].replace(0, np.nan)

    metric_labels = {
        "open_rate":    "Open Rate",
        "ctr":          "CTR (Click/Open)",
        "paid_rate":    "Paid Rate",
        "paid_credits": "Paid Credits",
        "deliveries":   "Deliveries",
    }
    metric_choice = st.selectbox(
        "Оберіть метрику",
        list(metric_labels.keys()),
        format_func=lambda k: metric_labels[k],
    )

    daily_clean = daily.dropna(subset=[metric_choice])
    fig_trend = px.line(
        daily_clean, x="Date", y=metric_choice,
        title=f"{metric_labels[metric_choice]} over time",
        markers=True,
    )

    # Лінія тренду
    if len(daily_clean) > 2:
        x_idx = np.arange(len(daily_clean))
        y_arr = daily_clean[metric_choice].values
        b, a  = np.polynomial.polynomial.polyfit(x_idx, y_arr, 1)
        fig_trend.add_scatter(
            x=daily_clean["Date"], y=a + b * x_idx,
            mode="lines", name="Trend",
            line=dict(dash="dash", color="red"),
        )
 # Аномалії (±2σ)
    mean_v, std_v = daily_clean[metric_choice].mean(), daily_clean[metric_choice].std()
    if std_v > 0:
        anomalies = daily_clean[abs(daily_clean[metric_choice] - mean_v) > 2 * std_v]
        if not anomalies.empty:
            fig_trend.add_scatter(
                x=anomalies["Date"], y=anomalies[metric_choice],
                mode="markers", name="Anomaly ⚠️",
                marker=dict(color="red", size=14, symbol="x"),
            )
    st.plotly_chart(fig_trend, use_container_width=True)

    # ── Month-over-month ────────────────────────────────
    st.subheader("🚨 Critical Changes (Month-over-Month)")

    df["month"] = df["date"].dt.to_period("M")
    monthly = (
        df.groupby("month")
        .agg(
            deliveries   =("delivery_id",     "nunique"),
            opens        =("is_open",          "sum"),
            clicks       =("is_click",         "sum"),
            paid         =("is_paid",          "sum"),
            paid_credits =("not_free_credits", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )
    monthly["open_rate"] = monthly["opens"]  / monthly["deliveries"].replace(0, np.nan)
    monthly["ctr"]       = monthly["clicks"] / monthly["opens"].replace(0, np.nan)
    monthly["paid_rate"] = monthly["paid"]   / monthly["clicks"].replace(0, np.nan)

    if len(monthly) >= 2:
        curr, prev = monthly.iloc[-1], monthly.iloc[-2]

        mom_cols = st.columns(4)
        for i, (key, label) in enumerate([
            ("open_rate",   "Open Rate"),
            ("ctr",         "CTR"),
            ("paid_rate",   "Paid Rate"),
            ("deliveries",  "Deliveries"),
        ]):
            c_val = curr[key]
            p_val = prev[key]
            if pd.notna(p_val) and p_val > 0:
                change = (c_val - p_val) / p_val
                fmt    = f"{c_val:.1%}" if key != "deliveries" else f"{int(c_val):,}"
                mom_cols[i].metric(label, fmt, f"{change:+.1%}")
                if abs(change) > ANOMALY_THRESHOLD:
                    mom_cols[i].error(f"⚠️ Критична зміна: {change:+.1%}")
    else:
        st.warning("Недостатньо даних для MoM-порівняння.")

    # ── Response type breakdown ─────────────────────────
    if "response" in df.columns:
        st.subheader("📬 Ефективність по типу повідомлення")
        resp_agg = (
            df.groupby("response")
            .agg(
                deliveries   =("delivery_id",     "nunique"),
                opens        =("is_open",          "sum"),
                clicks       =("is_click",         "sum"),
                paid         =("is_paid",          "sum"),
                paid_credits =("not_free_credits", "sum"),
            )
            .reset_index()
        )
        resp_agg["open_rate"] = resp_agg["opens"]  / resp_agg["deliveries"].replace(0, np.nan)
        resp_agg["ctr"]       = resp_agg["clicks"] / resp_agg["opens"].replace(0, np.nan)
        resp_agg["paid_rate"] = resp_agg["paid"]   / resp_agg["clicks"].replace(0, np.nan)
        resp_agg["avg_credits"] = resp_agg["paid_credits"] / resp_agg["clicks"].replace(0, np.nan)
        st.dataframe(
            resp_agg.style.format({
                "open_rate": "{:.1%}", "ctr": "{:.1%}",
                "paid_rate": "{:.1%}", "avg_credits": "{:.1f}",
                "paid_credits": "{:,.0f}",
            }),
            use_container_width=True,
        )
 # ── Rule breakdown ──────────────────────────────────
    rule_col = next((c for c in df.columns if c.lower() == "rule"), None)
    if rule_col:
        st.subheader("📋 Ефективність по Rule (сегмент відправки)")
        rule_agg = (
            df.groupby(rule_col)
            .agg(
                deliveries   =("delivery_id",     "nunique"),
                opens        =("is_open",          "sum"),
                clicks       =("is_click",         "sum"),
                paid         =("is_paid",          "sum"),
                paid_credits =("not_free_credits", "sum"),
            )
            .reset_index()
        )
        rule_agg["open_rate"]   = rule_agg["opens"]  / rule_agg["deliveries"].replace(0, np.nan)
        rule_agg["ctr"]         = rule_agg["clicks"] / rule_agg["opens"].replace(0, np.nan)
        rule_agg["paid_rate"]   = rule_agg["paid"]   / rule_agg["clicks"].replace(0, np.nan)
        rule_agg["avg_credits"] = rule_agg["paid_credits"] / rule_agg["clicks"].replace(0, np.nan)
        st.dataframe(
            rule_agg.style.format({
                "open_rate": "{:.1%}", "ctr": "{:.1%}",
                "paid_rate": "{:.1%}", "avg_credits": "{:.1f}",
            }),
            use_container_width=True,
        )

    # ── AI Summary ──────────────────────────────────────
    st.subheader("🤖 AI-згенероване самарі")
    if st.button("Згенерувати самарі", key="btn_monitoring_ai"):
        with st.spinner("Генерую..."):
            mom_open  = f"{(curr['open_rate']-prev['open_rate'])/prev['open_rate']:+.1%}" \
                        if len(monthly) >= 2 and prev["open_rate"] > 0 else "N/A"
            mom_ctr   = f"{(curr['ctr']-prev['ctr'])/prev['ctr']:+.1%}" \
                        if len(monthly) >= 2 and prev["ctr"] > 0 else "N/A"
            mom_paid  = f"{(curr['paid_rate']-prev['paid_rate'])/prev['paid_rate']:+.1%}" \
                        if len(monthly) >= 2 and prev["paid_rate"] > 0 else "N/A"

            prompt = f"""
You are a data analyst for a premium dating app (credits-based monetization, US market).
Analyze the email campaign metrics below and write a concise business summary (4-6 sentences).
Focus on funnel drop-off points, monetization health, and what to investigate or test next.

Period: {s_date} – {e_date}  |  Segment: {segment_filter}

Funnel:
- Deliveries: {deliveries:,}
- Open rate: {open_rate:.1%}
- CTR (Click/Open): {ctr:.1%}
- Paid rate (paid credits after click / clicks): {paid_rate:.1%}
- Total paid credits: {total_creds:,.0f}

Month-over-month change (latest vs previous):
- Open rate: {mom_open}
- CTR: {mom_ctr}
- Paid rate: {mom_paid}

Reply in the same language the analyst would use (Ukrainian or English is fine).
"""
            st.info(get_ai_summary(prompt))


# ═══════════════════════════════════════════════════════
# TAB 2 — A/B ANALYSIS
# ═══════════════════════════════════════════════════════
with tab2:

    group_cols = [c for c in df.columns if "group" in c.lower()]

    if not group_cols:
        st.warning("У даних не знайдено колонок з A/B тестами.")
    else:
        selected_group = st.selectbox("Оберіть експеримент", group_cols)

        df_g = df.dropna(subset=[selected_group])
        vals = df_g[selected_group].unique()

        # явно знаходимо control і test без залежності від порядку рядків
        control_val = next((v for v in vals if str(v).lower() == "control"), None)
        test_val    = next((v for v in vals if str(v).lower() == "test"),    None)

        if control_val is None or test_val is None:
            st.warning(
                f"У колонці '{selected_group}' не знайдено значень 'Control'/'Test'. "
                f"Знайдено: {list(vals)}"
            )
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

            # ── Порівняльна таблиця ─────────────────────
            st.subheader("📊 Порівняння метрик")

            cmp_df = pd.DataFrame({
                "Metric":   ["Deliveries", "Open rate", "CTR (Click/Open)",
                             "Paid rate", "Avg paid credits/click"],
                "Control":  [
                    f"{ctrl['deliveries']:,}",
                    f"{ctrl['open_rate']:.2%}",
                    f"{ctrl['ctr']:.2%}",
                    f"{ctrl['paid_rate']:.2%}",
                    f"{ctrl['avg_creds']:.1f}",
                ],
                "Test": [
                    f"{test['deliveries']:,}",
                    f"{test['open_rate']:.2%}",
                    f"{test['ctr']:.2%}",
                    f"{test['paid_rate']:.2%}",
                    f"{test['avg_creds']:.1f}",
                ],
            })
            st.dataframe(cmp_df, use_container_width=True)

            # ── Visual bars ─────────────────────────────
            bar_df = pd.DataFrame({
                "Group":     ["Control", "Test"] * 3,
                "Metric":    ["Open rate"] * 2 + ["CTR"] * 2 + ["Paid rate"] * 2,
                "Value":     [
                    ctrl["open_rate"], test["open_rate"],
                    ctrl["ctr"],       test["ctr"],
                    ctrl["paid_rate"], test["paid_rate"],
                ],
            })
            fig_ab = px.bar(
                bar_df, x="Metric", y="Value", color="Group",
                barmode="group", text_auto=".2%",
                title=f"Metrics: Control vs Test ({selected_group})",
                color_discrete_map={"Control": "#636EFA", "Test": "#EF553B"},
            )
            fig_ab.update_yaxes(tickformat=".1%")
            st.plotly_chart(fig_ab, use_container_width=True)

            # ── Stat tests ──────────────────────────────
            st.subheader("📐 Статистична значущість")

            def chi2_with_ci(n1, k1, n2, k2, alpha=0.05):
                """Chi-square + 95% CI для різниці пропорцій"""
                p1 = k1 / n1 if n1 else 0
                p2 = k2 / n2 if n2 else 0
                table = np.array([[k1, n1 - k1], [k2, n2 - k2]])
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
            r_ctr  = chi2_with_ci(ctrl["opens"],       ctrl["clicks"],
                                   test["opens"],       test["clicks"])
            r_paid = chi2_with_ci(ctrl["clicks"],      ctrl["paid"],
                                   test["clicks"],      test["paid"])
 def sig_badge(p):
                if p is None: return "⚠️ N/A (мало даних)"
                if p < 0.01:  return f"✅ p={p:.4f} (highly significant)"
                if p < 0.05:  return f"✅ p={p:.4f} (significant)"
                return              f"❌ p={p:.4f} (not significant)"

            def ci_str(ci):
                if ci is None: return "N/A"
                return f"[{ci[0]:+.2%}, {ci[1]:+.2%}]"

            def upl_str(u):
                return f"{u:+.1%}" if u is not None else "N/A"

            stat_df = pd.DataFrame({
                "Metric":       ["Open rate", "CTR", "Paid rate"],
                "Control":      [f"{r_open[0]:.2%}", f"{r_ctr[0]:.2%}", f"{r_paid[0]:.2%}"],
                "Test":         [f"{r_open[1]:.2%}", f"{r_ctr[1]:.2%}", f"{r_paid[1]:.2%}"],
                "Uplift":       [upl_str(r_open[3]), upl_str(r_ctr[3]), upl_str(r_paid[3])],
                "95% CI (diff)":[ci_str(r_open[4]),  ci_str(r_ctr[4]),  ci_str(r_paid[4])],
                "Significance": [sig_badge(r_open[2]),sig_badge(r_ctr[2]),sig_badge(r_paid[2])],
            })
            st.dataframe(stat_df, use_container_width=True)

            # ── Decision ────────────────────────────────
            st.subheader("🏁 Рішення по тесту")

            primary_sig    = r_paid[2] is not None and r_paid[2] < SIGNIFICANCE_LEVEL
            primary_uplift = r_paid[3] if r_paid[3] is not None else 0
            # Guardrail: CTR не повинен впасти більш ніж на 5%
            # (CTR — окрема метрика від paid_rate, тому це справжній guardrail)
            guardrail_ok   = r_ctr[3] is None or r_ctr[3] >= -0.05

            if primary_sig and primary_uplift > MIN_LIFT and guardrail_ok:
                st.success(
                    "🚀 Рекомендуємо rollout — значущий приріст paid rate, "
                    "guardrail (CTR) пройдено"
                )
            elif primary_sig and not guardrail_ok:
                st.error(
                    "🛑 Guardrail не пройдено — CTR впав суттєво. "
                    "Rollout не рекомендується без додаткового аналізу"
                )
            elif primary_sig:
                st.info(
                    "⚠️ Статистично значущо, але приріст нижче бізнес-порогу (5%). "
                    "Розглянь продовження тесту або перегляд гіпотези"
                )
            else:
                st.warning(
                    "❌ Немає значущого ефекту на paid rate. "
                    "Rollout не рекомендується"
                )

            # ── AI Recommendation ───────────────────────
            st.subheader("🤖 AI-рекомендація по тесту")
            if st.button("Згенерувати рекомендацію", key=f"btn_ab_{selected_group}"):
                with st.spinner("Генерую..."):
                    prompt = f"""
You are a senior data analyst for a premium dating app (credits-based, US market).
Analyze this A/B test and write a concise recommendation (5-7 sentences).
Cover: statistical validity, business impact on revenue (credits), what the pattern means, next steps.

Experiment: {selected_group}
Sample sizes: Control={ctrl['deliveries']:,}, Test={test['deliveries']:,}

| Metric    | Control          | Test             | Uplift             | p-value         | Significant |
|-----------|------------------|------------------|--------------------|-----------------|-------------|
| Open rate | {r_open[0]:.2%} | {r_open[1]:.2%} | {upl_str(r_open[3])} | {f"{r_open[2]:.4f}" if r_open[2] else "N/A"} | {r_open[2] is not None and r_open[2] < 0.05} |
| CTR       | {r_ctr[0]:.2%}  | {r_ctr[1]:.2%}  | {upl_str(r_ctr[3])}  | {f"{r_ctr[2]:.4f}"  if r_ctr[2]  else "N/A"} | {r_ctr[2]  is not None and r_ctr[2]  < 0.05} |
| Paid rate | {r_paid[0]:.2%} | {r_paid[1]:.2%} | {upl_str(r_paid[3])} | {f"{r_paid[2]:.4f}" if r_paid[2] else "N/A"} | {r_paid[2] is not None and r_paid[2] < 0.05} |
Avg paid credits: Control={ctrl['avg_creds']:.1f}, Test={test['avg_creds']:.1f}
Guardrail (CTR not dropped): {"PASSED" if guardrail_ok else "FAILED"}
Decision: {"Rollout" if primary_sig and primary_uplift > MIN_LIFT and guardrail_ok else "No rollout"}

Reply in Ukrainian.
"""
                    st.info(get_ai_summary(prompt))


# ═══════════════════════════════════════════════════════
# TAB 3 — SEGMENTS
# ═══════════════════════════════════════════════════════
with tab3:

    st.subheader("👥 Buyers vs Non-buyers")

    seg_agg = (
        df.groupby("is_buyer")
        .agg(
            deliveries   =("delivery_id",     "nunique"),
            opens        =("is_open",          "sum"),
            clicks       =("is_click",         "sum"),
            paid         =("is_paid",          "sum"),
            total_credits=("not_free_credits", "sum"),
        )
        .reset_index()
    )
    seg_agg["label"]       = seg_agg["is_buyer"].map({True: "Buyers", False: "Non-buyers"})
    seg_agg["open_rate"]   = seg_agg["opens"]  / seg_agg["deliveries"].replace(0, np.nan)
    seg_agg["ctr"]         = seg_agg["clicks"] / seg_agg["opens"].replace(0, np.nan)
    seg_agg["paid_rate"]   = seg_agg["paid"]   / seg_agg["clicks"].replace(0, np.nan)
    seg_agg["avg_credits"] = seg_agg["total_credits"] / seg_agg["clicks"].replace(0, np.nan)

    display_cols = ["label", "deliveries", "open_rate", "ctr",
                    "paid_rate", "avg_credits", "total_credits"]
    st.dataframe(
        seg_agg[display_cols].style.format({
            "open_rate":     "{:.1%}",
            "ctr":           "{:.1%}",
            "paid_rate":     "{:.1%}",
            "avg_credits":   "{:.1f}",
            "total_credits": "{:,.0f}",
            "deliveries":    "{:,}",
        }),
        use_container_width=True,
    )

    # Grouped bar — segments
    seg_bar = seg_agg.melt(
        id_vars="label",
        value_vars=["open_rate", "ctr", "paid_rate"],
        var_name="Metric", value_name="Value",
    )
    fig_seg = px.bar(
        seg_bar, x="Metric", y="Value", color="label",
        barmode="group", text_auto=".1%",
        title="Funnel метрики: Buyers vs Non-buyers",
        color_discrete_map={"Buyers": "#00CC96", "Non-buyers": "#AB63FA"},
    )
    fig_seg.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig_seg, use_container_width=True)

    # ── Trend by segment ───────────────────────────────
    st.subheader("📈 Тренди по сегменту")

    daily_seg = (
        df.groupby([df["date"].dt.date, "is_buyer"])
        .agg(
            open_rate  =("is_open",  "mean"),
            ctr        =("is_click", "mean"),
            paid_rate  =("is_paid",  "mean"),
        )
        .reset_index()
    )
    daily_seg["Segment"] = daily_seg["is_buyer"].map({True: "Buyers", False: "Non-buyers"})

    seg_metric = st.selectbox(
        "Метрика по сегменту",
        ["open_rate", "ctr", "paid_rate"],
        format_func=lambda k: {"open_rate": "Open Rate",
                               "ctr": "CTR", "paid_rate": "Paid Rate"}[k],
    )
    fig_seg_trend = px.line(
        daily_seg, x="date", y=seg_metric, color="Segment",
        title=f"{seg_metric} по сегменту",
        color_discrete_map={"Buyers": "#00CC96", "Non-buyers": "#AB63FA"},
    )
    st.plotly_chart(fig_seg_trend, use_container_width=True)
 # ── Credits distribution ───────────────────────────
    st.subheader("💰 Розподіл paid credits по сегменту")
    cred_df = df[df["not_free_credits"] > 0]
    if not cred_df.empty:
        cred_df = cred_df.copy()
        cred_df["Segment"] = cred_df["is_buyer"].map({True: "Buyers", False: "Non-buyers"})
        fig_creds = px.histogram(
            cred_df, x="not_free_credits", color="Segment",
            nbins=50, barmode="overlay", opacity=0.7,
            title="Розподіл paid credits (після кліку з email)",
            color_discrete_map={"Buyers": "#00CC96", "Non-buyers": "#AB63FA"},
        )
        st.plotly_chart(fig_creds, use_container_width=True)
    else:
        st.info("Немає записів з paid credits > 0 у вибраному фільтрі.")
