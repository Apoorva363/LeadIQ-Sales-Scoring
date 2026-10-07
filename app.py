
import os, json, re
from pathlib import Path
import pandas as pd
import streamlit as st
from google import genai

st.set_page_config(page_title="LeadIQ | Sales Lead Scoring",page_icon="◉",layout="wide",initial_sidebar_state="expanded")

st.markdown("""<style>
.stApp{background:#f7f5f0;color:#263434} section[data-testid="stSidebar"]{background:#eeeae2;border-right:1px solid #ddd7cc}
.brand{font-size:27px;font-weight:750;color:#173f3f}.subtitle{color:#6b7470;font-size:13px;margin-bottom:22px}
.section-title{color:#173f3f;font-size:21px;font-weight:700}.section-note{color:#727a76;font-size:13px}
.kpi{background:#fffdf9;border:1px solid #ded9cf;border-radius:12px;padding:16px;min-height:105px}
.kpi-label{color:#747b77;font-size:12px;text-transform:uppercase;letter-spacing:.7px}.kpi-value{color:#173f3f;font-size:29px;font-weight:750;margin-top:8px}.kpi-small{color:#7b817e;font-size:12px}
.panel{background:#fffdf9;border:1px solid #ded9cf;border-radius:12px;padding:18px}.tier{display:inline-block;padding:5px 11px;border-radius:20px;font-size:12px;font-weight:700}
.hot{background:#f6ddd6;color:#9d3f2e}.warm{background:#f4e7c9;color:#8a671e}.cold{background:#dce9e6;color:#2d6660}
.lead-row{display:flex;justify-content:space-between;align-items:center;padding:11px 0;border-bottom:1px solid #ece7df}.lead-name{font-weight:650}.lead-meta{font-size:12px;color:#7a817d}.score{font-size:18px;font-weight:750;color:#173f3f}
.bar-track{height:9px;background:#e9e5dd;border-radius:8px;overflow:hidden;margin-top:6px}.bar-fill{height:100%;border-radius:8px}
.signal-box{background:#f3f0ea;border:1px solid #e2ddd4;border-radius:10px;padding:12px 14px;margin-bottom:10px}.signal-title{color:#69726e;font-size:11px;text-transform:uppercase}.signal-value{font-size:16px;font-weight:650;margin-top:3px}
.ai-box{background:#eef3f1;border-left:4px solid #2f6861;border-radius:9px;padding:15px 17px;margin-top:12px}.action-box{background:#fff4ed;border-left:4px solid #d97758;border-radius:9px;padding:15px 17px;margin-top:12px}.footer{color:#858b87;font-size:11px;text-align:center;margin-top:35px;padding-top:14px;border-top:1px solid #e1ddd5}
</style>""",unsafe_allow_html=True)

REQ=["name","industry","budget","website_visits","brochure_download","site_visit","email_opens","purchase_timeline","days_since_last_interaction"]
SAMPLE=Path(__file__).parent/"sample_leads.csv"

def money(v):
    if pd.isna(v): return 0.0
    if isinstance(v,(int,float)): return float(v)
    s=str(v).lower().replace(",","").replace("₹","").replace("rs.","").replace("rs","").strip()
    try:
        n=float(re.sub(r"[^0-9.]","",s))
        return n*100 if "cr" in s else n
    except: return 0.0

def yes(v):
    return 1 if str(v).strip().lower() in {"yes","y","true","1","done","completed"} else 0

def num(v,d=0):
    try:
        if pd.isna(v): return d
        return float(v)
    except:
        try:return float(re.sub(r"[^0-9.]","",str(v)))
        except:return d

def timeline(v):
    s=str(v).lower()
    if any(x in s for x in ["immediate","this week","within 2 weeks","within 1 month","this month"]): return 20
    if any(x in s for x in ["1-3 months","within 3 months","next 3 months"]): return 14
    if any(x in s for x in ["3-6 months","within 6 months"]): return 8
    if any(x in s for x in ["6-12 months","within 12 months"]): return 4
    return 0

def score(r):
    s=0; reasons=[]
    b=money(r["budget"]); v=num(r["website_visits"]); br=yes(r["brochure_download"]); sv=yes(r["site_visit"]); e=num(r["email_opens"]); d=num(r["days_since_last_interaction"],999)
    if b>=100:s+=20;reasons.append("Budget is strongly aligned with the offering.")
    elif b>=50:s+=12;reasons.append("Budget shows reasonable purchase potential.")
    elif b>=25:s+=6;reasons.append("Budget indicates some purchase potential.")
    tp=timeline(r["purchase_timeline"]);s+=tp
    if tp==20:reasons.append("Purchase timeline is immediate.")
    elif tp==14:reasons.append("Purchase is likely within the next three months.")
    if sv:s+=20;reasons.append("Lead has completed a site visit, a strong buying signal.")
    if v>=10:s+=15;reasons.append("Website activity is high.")
    elif v>=5:s+=9
    elif v>=2:s+=4
    if br:s+=10;reasons.append("Lead has downloaded the brochure.")
    if e>=5:s+=10;reasons.append("Email engagement is strong.")
    elif e>=2:s+=6
    if d<=3:s+=5;reasons.append("Recent interaction indicates active interest.")
    elif d<=7:s+=3
    elif d>=15:reasons.append("Lead has not interacted recently.")
    s=int(min(s,100));t="Hot" if s>=80 else "Warm" if s>=50 else "Cold"
    return s,t,reasons

def prep(df):
    df=df.copy()
    for c in REQ:
        if c not in df: df[c]=0 if c not in ["name","industry","purchase_timeline"] else ""
    df["budget_lakh"]=df["budget"].apply(money)
    df["brochure_download"]=df["brochure_download"].apply(lambda x:"Yes" if yes(x) else "No")
    df["site_visit"]=df["site_visit"].apply(lambda x:"Yes" if yes(x) else "No")
    df["score"],df["tier"],df["score_reasons"]=zip(*df.apply(score,axis=1))
    return df

@st.cache_data
def sample(): return prep(pd.read_csv(SAMPLE))

def client():
    key=os.getenv("GEMINI_API_KEY","").strip()
    if not key:
        try:key=st.secrets["GEMINI_API_KEY"].strip()
        except:key=""
    return genai.Client(api_key=key) if key else None

def ai(r):
    c=client()
    if not c:return {"explanation":"Gemini is not connected.","follow_up":"Review the lead manually and contact them based on their purchase timeline.","risk":"GEMINI_API_KEY is not available."}
    prompt=f"""You are a practical sales manager. Lead: {r['name']}, Industry: {r['industry']}, Budget: {r['budget']} ({r['budget_lakh']} lakh), Website visits: {r['website_visits']}, Brochure: {r['brochure_download']}, Site visit: {r['site_visit']}, Email opens: {r['email_opens']}, Timeline: {r['purchase_timeline']}, Days since interaction: {r['days_since_last_interaction']}, Score: {r['score']}/100, Tier: {r['tier']}. Do not change score/tier. Return JSON with explanation (2-3 sentences), follow_up (one specific action), risk (one sentence)."""
    try:
        x=c.models.generate_content(model="gemini-3.5-flash-lite",contents=prompt,config={"response_mime_type":"application/json"})
        return json.loads(x.text)
    except Exception as e:return {"explanation":"The score was generated, but Gemini could not return an explanation.","follow_up":"Follow up based on the lead's buying timeline.","risk":str(e)[:160]}

if "leads_df" not in st.session_state: st.session_state["leads_df"]=sample()
df=st.session_state["leads_df"]

with st.sidebar:
    st.markdown('<div class="brand">LeadIQ</div><div class="subtitle">Sales lead scoring assistant</div>',unsafe_allow_html=True)
    page=st.radio("Go to",["Overview","Analyze Lead","Data"],label_visibility="collapsed")
    st.markdown("---");st.caption("Scoring model");st.caption("Budget · Intent · Engagement · Recency");st.caption("Gemini explains the score and suggests follow-up.")
    if st.button("Reset to sample data",width="stretch"):st.session_state["leads_df"]=sample();st.rerun()

st.markdown('<div class="section-title">Sales Lead Scoring Assistant</div><div class="section-note">A decision-support tool that turns lead activity into a clear sales priority.</div>',unsafe_allow_html=True)

if page=="Overview":
    total=len(df);hot=int((df.tier=="Hot").sum());warm=int((df.tier=="Warm").sum());cold=int((df.tier=="Cold").sum());avg=round(df.score.mean(),1)
    cs=st.columns(5)
    for c,(l,v,n) in zip(cs,[("Total leads",total,"in current dataset"),("Hot",hot,"priority leads"),("Warm",warm,"needs nurturing"),("Cold",cold,"low current intent"),("Avg. score",avg,"out of 100")]):
        c.markdown(f'<div class="kpi"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div><div class="kpi-small">{n}</div></div>',unsafe_allow_html=True)
    st.write("");a,b=st.columns([1,1.35])
    with a:
        st.markdown('<div class="panel"><b>Lead distribution</b>',unsafe_allow_html=True)
        hp=hot/total*100 if total else 0;wp=warm/total*100 if total else 0
        st.markdown(f'<div style="display:flex;align-items:center;gap:25px;padding:18px 4px"><div style="width:140px;height:140px;border-radius:50%;background:conic-gradient(#c95f49 0 {hp}%,#c7a45a {hp}% {hp+wp}%,#5f8d86 {hp+wp}% 100%);display:flex;align-items:center;justify-content:center"><div style="width:80px;height:80px;border-radius:50%;background:#fffdf9;display:flex;align-items:center;justify-content:center;font-size:25px;font-weight:750">{total}</div></div><div><div>🔴 Hot <b>{hot}</b></div><div>🟡 Warm <b>{warm}</b></div><div>🟢 Cold <b>{cold}</b></div></div></div></div>',unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel"><b>Lead scores</b>',unsafe_allow_html=True)
        for _,r in df.sort_values("score",ascending=False).head(10).iterrows():
            color="#c95f49" if r.tier=="Hot" else "#c7a45a" if r.tier=="Warm" else "#5f8d86"
            st.markdown(f'<div style="margin:12px 0"><div style="display:flex;justify-content:space-between"><b>{r["name"]}</b><span>{r["score"]}/100</span></div><div class="bar-track"><div class="bar-fill" style="width:{r["score"]}%;background:{color}"></div></div></div>',unsafe_allow_html=True)
        st.markdown("</div>",unsafe_allow_html=True)
    st.write("");a,b=st.columns([1.2,.8])
    with a:
        st.markdown("**Priority leads**")
        for _,r in df.sort_values("score",ascending=False).head(7).iterrows():
            st.markdown(f'<div class="lead-row"><div><div class="lead-name">{r["name"]}</div><div class="lead-meta">{r["industry"]} · {r["purchase_timeline"]}</div></div><div><span class="tier {r["tier"].lower()}">{r["tier"]}</span> <span class="score">{r["score"]}</span></div></div>',unsafe_allow_html=True)
    with b:
        st.markdown("**What needs attention?**")
        msg=f"{hot} hot lead{'s' if hot!=1 else ''} should be prioritised for direct sales follow-up." if hot else "Focus on the strongest warm leads."
        st.markdown(f'<div class="action-box"><b>Sales priority</b><br><br>{msg}</div>',unsafe_allow_html=True)
        st.markdown('<div class="ai-box"><b>How the AI fits in</b><br><br>The numerical score uses fixed business rules. Gemini interprets the signals and recommends a next action.</div>',unsafe_allow_html=True)

elif page=="Analyze Lead":
    selected=st.selectbox("Select a lead",df.name.astype(str).tolist());r=df[df.name.astype(str)==selected].iloc[0]
    a,b,c=st.columns(3)
    a.markdown(f'<div class="kpi"><div class="kpi-label">Lead score</div><div class="kpi-value">{r.score}/100</div><div class="kpi-small">rule-based</div></div>',unsafe_allow_html=True)
    b.markdown(f'<div class="kpi"><div class="kpi-label">Priority</div><div class="kpi-value"><span class="tier {r.tier.lower()}">{r.tier}</span></div><div class="kpi-small">classification</div></div>',unsafe_allow_html=True)
    c.markdown(f'<div class="kpi"><div class="kpi-label">Timeline</div><div class="kpi-value" style="font-size:21px">{r.purchase_timeline}</div><div class="kpi-small">buying intent</div></div>',unsafe_allow_html=True)
    st.write("");a,b=st.columns([1,1.15])
    with a:
        st.markdown("### Lead details")
        vals=[("Industry",r.industry),("Budget",f"{r.budget} ({r.budget_lakh:.0f} lakh)"),("Website visits",int(num(r.website_visits))),("Brochure downloaded",r.brochure_download),("Site visit",r.site_visit),("Email opens",int(num(r.email_opens))),("Days since interaction",int(num(r.days_since_last_interaction)))]
        for l,v in vals:st.markdown(f'<div class="signal-box"><div class="signal-title">{l}</div><div class="signal-value">{v}</div></div>',unsafe_allow_html=True)
        st.markdown("### Why this score?")
        for x in r.score_reasons:st.markdown(f"• {x}")
    with b:
        st.markdown("### AI interpretation")
        if st.button("Generate AI explanation",type="primary",width="stretch"):
            with st.spinner("Gemini is reviewing the lead..."):st.session_state["ai"]=ai(r)
            st.session_state["ai_lead"]=selected
        if st.session_state.get("ai_lead")==selected:
            x=st.session_state["ai"];st.markdown(f'<div class="ai-box"><b>Why this lead matters</b><br><br>{x["explanation"]}</div>',unsafe_allow_html=True);st.markdown(f'<div class="action-box"><b>Recommended follow-up</b><br><br>{x["follow_up"]}</div>',unsafe_allow_html=True);st.markdown(f'<div class="signal-box"><div class="signal-title">Main risk / gap</div><div class="signal-value" style="font-size:14px">{x["risk"]}</div></div>',unsafe_allow_html=True)

else:
    st.markdown("### Lead data");st.markdown('<div class="section-note">Upload a CSV with the same fields. Budget and Yes/No values are automatically normalized.</div>',unsafe_allow_html=True)
    up=st.file_uploader("Upload CSV",type=["csv"])
    if up:
        d=pd.read_csv(up);missing=[c for c in REQ if c not in d.columns]
        if missing:st.error("Missing required columns: "+", ".join(missing))
        else:st.session_state["leads_df"]=prep(d);df=st.session_state["leads_df"];st.success(f"Loaded {len(df)} leads.")
    st.dataframe(df[REQ+["budget_lakh","score","tier"]],hide_index=True,width="stretch")
    st.download_button("Download scored leads",data=df.to_csv(index=False).encode(),file_name="leadiq_scored_leads.csv",mime="text/csv",width="stretch")

st.markdown('<div class="footer">LeadIQ · MBA End-Term Project · Rule-based scoring + Gemini AI assistance</div>',unsafe_allow_html=True)
