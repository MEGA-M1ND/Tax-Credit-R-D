# R&D Tax Credit — AI Agent (MVP)

Short description
- AI-assisted tool to classify projects for IRS §41 R&D tax credit eligibility and generate supporting QRE and audit evidence.

Quick start (Windows / PowerShell)
1. Create a Python venv and install deps:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

2. Configure secrets locally (do NOT commit):
   # create a .env with OPENAI_API_KEY and OPENAI_MODEL
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini

3. Start backend (FastAPI):
   uvicorn app.main:app --reload --port 8000

4. Start the Streamlit UI:
   streamlit run streamlit_app.py

Notes
- .env and API keys must remain local. Use GitHub Secrets for CI.
- See IMPLEMENTATION_SUMMARY.md and QUICK_START.md for details.