# LeadIQ – AI-Powered Sales Lead Scoring & Follow-up Assistant

Academic end-term prototype based on Use Case 7: Sales lead-scoring assistant.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional Gemini setup:

**Windows PowerShell**
```powershell
$env:GEMINI_API_KEY="YOUR_KEY_HERE"
streamlit run app.py
```

The app works without Gemini as well; it falls back to deterministic scoring and a safe generic follow-up message.

## Demo data
Use the six synthetic leads included in the app or `sample_leads.csv`.

## Architecture
User input → validation → deterministic lead score → Hot/Warm/Cold tier → Gemini explanation + follow-up → export.
