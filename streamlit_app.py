import streamlit as st
import pandas as pd
import requests
import os
import json
from io import BytesIO

st.set_page_config(page_title="AI R&D Tax Credit Agent — MVP", layout="wide")
st.title("🧪 AI R&D Tax Credit Agent — MVP (Phase 1)")

backend_url = st.text_input("Backend URL", value=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))
user_id = st.text_input("User ID (for trace)", value="demo-user")

uploaded = st.file_uploader("Upload CSV (columns: project_id, project_name, description, cost, category)", type=["csv"])

colA, colB, colC, colD = st.columns(4)
with colA:
    tax_year = st.number_input("Tax Year", min_value=2000, max_value=2100, value=2024, step=1)
with colB:
    elect_280c = st.toggle("Elect §280C reduction", value=True)
with colC:
    method = st.selectbox("Method (initial)", options=["ASC", "REG"], index=0)
with colD:
    st.caption("Tip: ASC usually preferred if receipts/base lead to higher benefit.")

if uploaded and st.button("Analyze Projects"):
    with st.spinner("Classifying..."):
        try:
            resp = requests.post(f"{backend_url}/classify_rnd", files={"file": uploaded}, data={"user_id": user_id}, timeout=60)
            if resp.status_code == 200:
                payload = resp.json()
                results = payload.get("results") or []
                # Be defensive: if results is not list-like, wrap or fallback
                try:
                    df = pd.DataFrame(results)
                except Exception:
                    df = pd.DataFrame([])
                st.success(f"Processed {payload.get('count', len(df))} rows.")
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No results returned from backend.")

                # Show QRE roll-up if present
                qre_by_cat = payload.get("qre_by_category", {})
                if qre_by_cat:
                    qre_df = pd.DataFrame([{"category": k, "amount": v} for k, v in qre_by_cat.items()])
                    m1, m2 = st.columns(2)
                    with m1:
                        st.metric("Categories", len(qre_df))
                    with m2:
                        st.metric("QRE (sum, uploaded 'cost')", f"${qre_df['amount'].sum():,.2f}")
                    st.bar_chart(qre_df.set_index("category"))

                st.session_state["last_results"] = payload
            else:
                st.error(f"Error: {resp.status_code} -> {resp.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

st.markdown("---")

# Credit computation block
st.subheader("Compute Federal Credit (ASC vs Regular)")
with st.expander("Prior-Year QRE Inputs (for ASC/REG)"):
    c1, c2, c3 = st.columns(3)
    y1, y2, y3 = tax_year-1, tax_year-2, tax_year-3
    qre_y1 = c1.number_input(f"QRE {y1}", min_value=0.0, value=90000.0, step=1000.0)
    qre_y2 = c2.number_input(f"QRE {y2}", min_value=0.0, value=80000.0, step=1000.0)
    qre_y3 = c3.number_input(f"QRE {y3}", min_value=0.0, value=70000.0, step=1000.0)

cur_qre = st.number_input("Current-year QRE (demo total)", min_value=0.0, value=117700.0, step=1000.0)

if st.button("Compute Credit"):
    body = {
        "year": int(tax_year),
        "qre_current": float(cur_qre),
        "qre_prior_3yrs": {str(y1): qre_y1, str(y2): qre_y2, str(y3): qre_y3},
        "gross_receipts_prior_4yrs": {},  # optional in this MVP
        "elect_280c": bool(elect_280c),
        "method": method
    }
    try:
        r = requests.post(f"{backend_url}/compute_credit", json=body, timeout=60)
        if r.status_code == 200:
            out = r.json()
            credit = out["credit"]
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("ASC", f"${credit['credit_asc']:,.2f}")
            with m2:
                st.metric("Regular", f"${credit['credit_regular']:,.2f}")
            with m3:
                st.metric("Selected", f"${credit['credit_selected']:,.2f}")
            with m4:
                st.metric("Method", credit["method_selected"])
            st.json(out["form6765"])  # show lines/explanations for transparency
            st.session_state["last_credit"] = out
        else:
            st.error(f"Error: {r.status_code} -> {r.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")

st.markdown("---")
st.subheader("One-click Evidence Pack (ZIP)")

default_narr = "**Narrative**\n\nIRS-ready summary of eligible activities, uncertainties, and experimentation."
if "last_results" in st.session_state and "last_credit" in st.session_state:
    narrative_md = st.text_area("Narrative (Markdown)", value=default_narr, height=160)
    if st.button("Generate ZIP"):
        # Build a simple qre table for the ZIP (pull from last_results if any cost columns exist client-side)
        qre_rows = []
        # This is a lean placeholder; in a real run you'd pass your expense agent rows.
        qre_rows.append(["Senior ML engineer salary", 54000, "WAGES", True, 54000])
        qre_rows.append(["Junior DS", 22000, "WAGES", True, 22000])
        qre_rows.append(["Cloud GPU", 15000, "CLOUD", True, 15000])
        qre_rows.append(["CV contractor", 28000, "CONTRACTOR", True, 18200])
        qre_rows.append(["Sensors", 8500, "SUPPLIES", True, 8500])

        credit = st.session_state["last_credit"]["credit"]
        lines = [f"{k}: {v}" for k, v in credit["line_map"].items()]
        payload = {
            "run_id": f"run-{tax_year}",
            "form_lines": ["Form 6765 (Demo Preview)"] + lines,
            "qre_rows": qre_rows,
            "narrative_md": narrative_md,
            "traces": st.session_state["last_results"]  # bundle last traces/paths
        }
        try:
            z = requests.post(f"{backend_url}/evidence_pack", json=payload, timeout=60)
            if z.status_code == 200:
                st.success("Evidence pack generated.")
                st.download_button(
                    label="⬇️ Download Evidence Pack (ZIP)",
                    data=z.content,
                    file_name=f"{payload['run_id']}_evidence_pack.zip",
                    mime="application/zip"
                )
            else:
                st.error(f"Error: {z.status_code} -> {z.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")
else:
    st.info("Run classification and credit computation first, then generate the evidence pack.")

st.markdown("---")
st.caption("Tip: Start the backend with `uvicorn app.main:app --reload --port 8000` before running Streamlit.")
