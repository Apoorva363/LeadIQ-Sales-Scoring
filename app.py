
import os
import json
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai

st.set_page_config(
    page_title="LeadIQ | Sales Lead Scoring",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
    .stApp {
        background: #f7f5f0;
        color: #263434;
    }

    section[data-testid="stSidebar"] {
        background: #eeeae2;
        border-right: 1px solid #ddd7cc;
    }

    .brand {
        font-size: 27px;
        font-weight: 750;
        letter-spacing: -0.5px;
        color: #173f3f;
        margin-bottom: 2px;
    }

    .subtitle {
        color: #6b7470;
        font-size: 13px;
        margin-bottom: 22px;
    }

    .section-title {
        color: #173f3f;
        font-size: 21px;
        font-weight: 700;
        margin: 10px 0 3px 0;
    }

    .section-note {
        color: #727a76;
        font-size: 13px;
        margin-bottom: 15px;
    }

    .kpi {
        background: #fffdf9;
        border: 1px solid #ded9cf;
        border-radius: 12px;
        padding: 16px 17px;
        min-height: 105px;
        box-shadow: 0 1px 2px rgba(40,40,30,.03);
    }

    .kpi-label {
        color: #747b77;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: .7px;
    }

    .kpi-value {
        color: #173f3f;
        font-size: 29px;
        font-weight: 750;
        margin-top: 8px;
    }

    .kpi-small {
        color: #7b817e;
        font-size: 12px;
        margin-top: 2px;
    }

    .panel {
        background: #fffdf9;
        border: 1px solid #ded9cf;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 1px 2px rgba(40,40,30,.03);
    }

    .tier {
        display: inline-block;
        padding: 5px 11px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }

    .hot { background:#f6ddd6; color:#9d3f2e; }
    .warm { background:#f4e7c9; color:#8a671e; }
    .cold { background:#dce9e6; color:#2d6660; }

    .lead-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 14px;
        padding: 11px 0;
        border-bottom: 1px solid #ece7df;
    }

    .lead-row:last-child { border-bottom: none; }

    .lead-name { font-weight: 650; color:#263434; }
    .lead-meta { font-size: 12px; color:#7a817d; margin-top:2px; }

    .score {
        font-size: 18px;
        font-weight: 750;
        color: #173f3f;
        min-width: 48px;
        text-align: right;
    }

    .bar-track {
        height: 9px;
        background: #e9e5dd;
        border-radius: 8px;
        overflow: hidden;
        margin-top: 6px;
    }

    .bar-fill {
        height: 100%;
        border-radius: 8px;
    }

    .signal-box {
        background:#f3f0ea;
        border:1px solid #e2ddd4;
        border-radius:10px;
        padding:12px 14px;
        margin-bottom:10px;
    }

    .signal-title {
        color:#69726e;
        font-size:11px;
        text-transform:uppercase;
        letter-spacing:.6px;
    }

    .signal-value {
        color:#263434;
        font-size:16px;
        font-weight:650;
        margin-top:3px;
    }

    .ai-box {
        background:#eef3f1;
        border-left:4px solid #2f6861;
        border-radius:9px;
        padding:15px 17px;
        margin-top:12px;
    }

    .action-box {
        background:#fff4ed;
        border-left:4px solid #d97758;
        border-radius:9px;
        padding:15px 17px;
        margin-top:12px;
    }

    .footer {
        color:#858b87;
        font-size:11px;
        text-align:center;
        margin-top:35px;
        padding-top:14px;
        border-top:1px solid #e1ddd5;
    }

    div[data-testid="stMetric"] {
        background: #fffdf9;
        border: 1px solid #ded9cf;
        padding: 10px 13px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Data + scoring
# -----------------------------
REQUIRED_COLUMNS = [
    "name", "industry", "budget", "website_visits",
    "brochure_download", "site_visit", "email_opens",
    "purchase_timeline", "days_since_last_interaction"
]

SAMPLE_FILE = Path(__file__).parent / "sample_leads.csv"


def safe_num(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def score_lead(row):
    score = 0
    reasons = []

    budget = safe_num(row.get("budget"))
    visits = safe_num(row.get("website_visits"))
    brochure = safe_num(row.get("brochure_download"))
    site_visit = safe_num(row.get("site_visit"))
    emails = safe_num(row.get("email_opens"))
    timeline = str(row.get("purchase_timeline", "")).strip().lower()
    days = safe_num(row.get("days_since_last_interaction"), 999)

    # Budget fit: max 20
    if budget >= 100:
        score += 20
        reasons.append("Budget is strongly aligned with the offering.")
    elif budget >= 50:
        score += 12
        reasons.append("Budget shows reasonable purchase potential.")
    elif budget >= 25:
        score += 6

    # Purchase timeline: max 20
    if timeline in ["immediate", "this month", "within 1 month", "within 2 weeks"]:
        score += 20
        reasons.append("Purchase timeline is immediate.")
    elif timeline in ["1-3 months", "within 3 months", "next 3 months"]:
        score += 14
        reasons.append("Purchase is likely within the next three months.")
    elif timeline in ["3-6 months", "within 6 months"]:
        score += 8
    elif timeline:
        score += 3

    # Site visit: 20
    if site_visit >= 1:
        score += 20
        reasons.append("Lead has completed a site visit, a strong buying signal.")

    # Website engagement: 15
    if visits >= 10:
        score += 15
        reasons.append("Website activity is high.")
    elif visits >= 5:
        score += 9
    elif visits >= 2:
        score += 4

    # Brochure: 10
    if brochure >= 1:
        score += 10
        reasons.append("Lead has downloaded the brochure.")

    # Email: 10
    if emails >= 5:
        score += 10
        reasons.append("Email engagement is strong.")
    elif emails >= 2:
        score += 6

    # Recency: 5
    if days <= 3:
        score += 5
        reasons.append("Recent interaction indicates active interest.")
    elif days <= 7:
        score += 3

    score = int(min(score, 100))

    if score >= 80:
        tier = "Hot"
    elif score >= 50:
        tier = "Warm"
    else:
        tier = "Cold"

    return score, tier, reasons


def prepare_data(df):
    df = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = 0 if col not in ["name", "industry", "purchase_timeline"] else ""
    df["score"], df["tier"], df["score_reasons"] = zip(
        *df.apply(score_lead, axis=1)
    )
    return df


@st.cache_data
def load_sample():
    df = pd.read_csv(SAMPLE_FILE)
    return prepare_data(df)


def get_client():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


def ai_explain(row):
    client = get_client()
    if client is None:
        return {
            "explanation": "Gemini is not connected. The score and lead tier are still available from the rule-based scoring engine.",
            "follow_up": "Review the lead manually and contact them based on their purchase timeline.",
            "risk": "AI explanation unavailable until GEMINI_API_KEY is configured."
        }

    prompt = f"""
You are a practical sales manager helping an MBA student demonstrate a lead-scoring system.

Lead:
Name: {row['name']}
Industry: {row['industry']}
Budget: {row['budget']}
Website visits: {row['website_visits']}
Brochure downloaded: {row['brochure_download']}
Site visit: {row['site_visit']}
Email opens: {row['email_opens']}
Purchase timeline: {row['purchase_timeline']}
Days since last interaction: {row['days_since_last_interaction']}
Rule-based score: {row['score']}/100
Lead tier: {row['tier']}

Give a concise business interpretation. Do not change the score or tier.

Return valid JSON with exactly these keys:
explanation: 2-3 sentences explaining why this lead is important.
follow_up: one specific recommended sales follow-up.
risk: one short sentence describing the main risk or missing signal.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        return {
            "explanation": data.get("explanation", "No explanation returned."),
            "follow_up": data.get("follow_up", "Follow up based on the lead's buying timeline."),
            "risk": data.get("risk", "Review missing or weak engagement signals.")
        }
    except Exception as e:
        return {
            "explanation": "The rule-based score was generated successfully, but Gemini could not return an explanation.",
            "follow_up": "Use the lead's tier and purchase timeline to decide the next contact.",
            "risk": f"Gemini response error: {str(e)[:160]}"
        }


# -----------------------------
# Session data
# -----------------------------
if "leads_df" not in st.session_state:
    st.session_state["leads_df"] = load_sample()

df = st.session_state["leads_df"]

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown('<div class="brand">LeadIQ</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Sales lead scoring assistant</div>', unsafe_allow_html=True)

    page = st.radio(
        "Go to",
        ["Overview", "Analyze Lead", "Data"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("Scoring model")
    st.caption("Budget · Intent · Engagement · Recency")
    st.caption("Gemini is used for explanations and follow-up suggestions.")

    if st.button("Reset to sample data", width="stretch"):
        st.session_state["leads_df"] = load_sample()
        st.rerun()

# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="section-title">Sales Lead Scoring Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-note">A simple decision-support tool that turns lead activity into a clear sales priority.</div>',
    unsafe_allow_html=True
)

# -----------------------------
# Overview
# -----------------------------
if page == "Overview":
    total = len(df)
    hot = int((df["tier"] == "Hot").sum())
    warm = int((df["tier"] == "Warm").sum())
    cold = int((df["tier"] == "Cold").sum())
    avg = round(df["score"].mean(), 1) if total else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    cards = [
        ("Total leads", total, "in current dataset"),
        ("Hot", hot, "priority leads"),
        ("Warm", warm, "needs nurturing"),
        ("Cold", cold, "low current intent"),
        ("Avg. score", avg, "out of 100"),
    ]

    for col, (label, value, note) in zip([k1,k2,k3,k4,k5], cards):
        with col:
            st.markdown(
                f'<div class="kpi"><div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f'<div class="kpi-small">{note}</div></div>',
                unsafe_allow_html=True
            )

    st.write("")

    left, right = st.columns([1, 1.35])

    # Donut
    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("**Lead distribution**")
        if total:
            hot_pct = hot / total * 100
            warm_pct = warm / total * 100
            cold_pct = cold / total * 100
        else:
            hot_pct = warm_pct = cold_pct = 0

        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:28px;padding:12px 4px 8px 4px;">
              <div style="width:145px;height:145px;border-radius:50%;
                background:conic-gradient(#c95f49 0 {hot_pct}%,
                #c7a45a {hot_pct}% {hot_pct+warm_pct}%,
                #5f8d86 {hot_pct+warm_pct}% 100%);
                display:flex;align-items:center;justify-content:center;">
                <div style="width:83px;height:83px;border-radius:50%;
                  background:#fffdf9;display:flex;align-items:center;justify-content:center;
                  font-size:25px;font-weight:750;color:#173f3f;">{total}</div>
              </div>
              <div style="line-height:2;">
                <div><span style="color:#c95f49;">●</span> Hot &nbsp; <b>{hot}</b> ({hot_pct:.0f}%)</div>
                <div><span style="color:#c7a45a;">●</span> Warm &nbsp; <b>{warm}</b> ({warm_pct:.0f}%)</div>
                <div><span style="color:#5f8d86;">●</span> Cold &nbsp; <b>{cold}</b> ({cold_pct:.0f}%)</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Score bars
    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown("**Lead scores**")
        display_df = df.sort_values(["score", "name"], ascending=[False, True]).head(8)

        for _, r in display_df.iterrows():
            tier_class = str(r["tier"]).lower()
            fill = "#c95f49" if tier_class == "hot" else "#c7a45a" if tier_class == "warm" else "#5f8d86"
            st.markdown(
                f"""
                <div style="margin-bottom:12px;">
                  <div style="display:flex;justify-content:space-between;font-size:13px;">
                    <span><b>{r['name']}</b></span><span>{int(r['score'])}/100</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" style="width:{int(r['score'])}%;background:{fill};"></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    left, right = st.columns([1.25, .75])

    with left:
        st.markdown("**Priority leads**")
        priority = df.sort_values(["score", "name"], ascending=[False, True]).copy()
        for _, r in priority.head(6).iterrows():
            tier_class = str(r["tier"]).lower()
            st.markdown(
                f"""
                <div class="lead-row">
                    <div>
                        <div class="lead-name">{r['name']}</div>
                        <div class="lead-meta">{r['industry']} · {r['purchase_timeline']}</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span class="tier {tier_class}">{r['tier']}</span>
                        <span class="score">{int(r['score'])}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with right:
        st.markdown("**What needs attention?**")
        if hot:
            message = f"{hot} hot lead{'s' if hot != 1 else ''} should be prioritised for direct sales follow-up."
        elif warm:
            message = "No hot leads are currently available. Focus on moving the strongest warm leads forward."
        else:
            message = "Current leads show low intent. Focus on qualification and nurturing."
        st.markdown(
            f'<div class="action-box"><b>Sales priority</b><br><br>{message}</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="ai-box"><b>How the AI fits in</b><br><br>'
            'The score is calculated using fixed business rules for consistency. '
            'Gemini then interprets the signals and suggests a practical next action.</div>',
            unsafe_allow_html=True
        )

# -----------------------------
# Analyze Lead
# -----------------------------
elif page == "Analyze Lead":
    if df.empty:
        st.warning("No leads are available. Upload a CSV from the Data section.")
        st.stop()

    names = df["name"].astype(str).tolist()
    selected = st.selectbox("Select a lead", names)
    row = df[df["name"].astype(str) == selected].iloc[0]

    score = int(row["score"])
    tier = row["tier"]
    tier_class = tier.lower()

    a, b, c = st.columns([1, 1, 1])
    with a:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Lead score</div>'
            f'<div class="kpi-value">{score}/100</div>'
            f'<div class="kpi-small">rule-based score</div></div>',
            unsafe_allow_html=True
        )
    with b:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Priority</div>'
            f'<div class="kpi-value"><span class="tier {tier_class}">{tier}</span></div>'
            f'<div class="kpi-small">sales classification</div></div>',
            unsafe_allow_html=True
        )
    with c:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Purchase timeline</div>'
            f'<div class="kpi-value" style="font-size:22px;">{row["purchase_timeline"]}</div>'
            f'<div class="kpi-small">declared buying intent</div></div>',
            unsafe_allow_html=True
        )

    st.write("")
    left, right = st.columns([1, 1.15])

    with left:
        st.markdown("### Lead details")
        details = [
            ("Industry", row["industry"]),
            ("Budget", f"{row['budget']}"),
            ("Website visits", int(safe_num(row["website_visits"]))),
            ("Brochure downloaded", "Yes" if safe_num(row["brochure_download"]) else "No"),
            ("Site visit", "Yes" if safe_num(row["site_visit"]) else "No"),
            ("Email opens", int(safe_num(row["email_opens"]))),
            ("Days since interaction", int(safe_num(row["days_since_last_interaction"], 0))),
        ]
        for label, value in details:
            st.markdown(
                f'<div class="signal-box"><div class="signal-title">{label}</div>'
                f'<div class="signal-value">{value}</div></div>',
                unsafe_allow_html=True
            )

        st.markdown("### Why this score?")
        if row["score_reasons"]:
            for reason in row["score_reasons"]:
                st.markdown(f"• {reason}")
        else:
            st.caption("No strong positive signals were detected.")

    with right:
        st.markdown("### AI interpretation")
        if st.button("Generate AI explanation", type="primary", width="stretch"):
            with st.spinner("Gemini is reviewing the lead..."):
                result = ai_explain(row)
            st.session_state["last_ai_result"] = result
            st.session_state["last_ai_lead"] = selected

        if (
            st.session_state.get("last_ai_lead") == selected
            and "last_ai_result" in st.session_state
        ):
            result = st.session_state["last_ai_result"]
            st.markdown(
                f'<div class="ai-box"><b>Why this lead matters</b><br><br>{result["explanation"]}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="action-box"><b>Recommended follow-up</b><br><br>{result["follow_up"]}</div>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div class="signal-box"><div class="signal-title">Main risk / gap</div>'
                f'<div class="signal-value" style="font-size:14px;">{result["risk"]}</div></div>',
                unsafe_allow_html=True
            )
        else:
            st.info("Click the button to generate a Gemini-powered explanation and follow-up recommendation.")

# -----------------------------
# Data
# -----------------------------
else:
    st.markdown("### Lead data")
    st.markdown(
        '<div class="section-note">Use the sample dataset for the demo, or upload your own CSV with the same fields.</div>',
        unsafe_allow_html=True
    )

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is not None:
        try:
            uploaded_df = pd.read_csv(uploaded)
            missing = [c for c in REQUIRED_COLUMNS if c not in uploaded_df.columns]
            if missing:
                st.error("Missing required columns: " + ", ".join(missing))
            else:
                st.session_state["leads_df"] = prepare_data(uploaded_df)
                df = st.session_state["leads_df"]
                st.success(f"Loaded {len(df)} leads.")
        except Exception as e:
            st.error(f"Could not read the CSV: {e}")

    st.dataframe(
        df[REQUIRED_COLUMNS + ["score", "tier"]],
        hide_index=True,
        width="stretch"
    )

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download scored leads",
        data=csv_bytes,
        file_name="leadiq_scored_leads.csv",
        mime="text/csv",
        width="stretch"
    )

st.markdown(
    '<div class="footer">LeadIQ · MBA End-Term Project · Rule-based scoring + Gemini AI assistance</div>',
    unsafe_allow_html=True
)
