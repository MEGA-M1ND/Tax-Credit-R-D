import streamlit as st
import pandas as pd
import requests
import os

st.set_page_config(page_title="AI R&D Tax Credit Agent - MVP", layout="wide")

st.title("AI R&D Tax Credit Agent - MVP (Phase 1)")
st.write("Upload a CSV of project descriptions to classify R&D tax credit eligibility and export supporting documents.")

backend_url = st.text_input(
    "Backend URL",
    value=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"),
)
user_id = st.text_input("User ID (for trace)", value="demo-user")
api_key = st.text_input("API Key (X-API-Key)", type="password")

uploaded = st.file_uploader("Upload CSV", type=["csv"])

results_df = st.session_state.get("results_df", None)

if uploaded and st.button("Analyze"):
    if not api_key:
        st.error("API key is required.")
    else:
        with st.spinner("Classifying... (this may take a minute)"):
            try:
                resp = requests.post(
                    f"{backend_url}/classify_rnd",
                    files={"file": uploaded},
                    data={"user_id": user_id},
                    headers={"X-API-Key": api_key},
                    timeout=300,  # 5 minute timeout for classification
                )
                if resp.status_code == 200:
                    payload = resp.json()
                    if "results" in payload:
                        results_df = pd.DataFrame(payload["results"])
                        st.session_state["results_df"] = results_df
                        st.success(f"Processed {payload.get('count', len(results_df))} rows.")
                        st.dataframe(results_df, use_container_width=True)
                    else:
                        st.error(payload)
                else:
                    st.error(f"Error: {resp.status_code} -> {resp.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")

# Reload results if they exist in session
if results_df is not None and not results_df.empty:
    st.markdown("### Export Tools")
    project_ids = results_df["project_id"].astype(str).tolist()
    selected_project = st.selectbox("Select Project ID", project_ids)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Download Form 6765 PDF"):
            if not api_key:
                st.error("API key is required.")
            else:
                try:
                    resp = requests.post(
                        f"{backend_url}/generate_form_6765",
                        data={"project_id": selected_project},
                        headers={"X-API-Key": api_key},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        pdf_bytes = resp.content
                        st.download_button(
                            label="Save Form 6765 PDF",
                            data=pdf_bytes,
                            file_name=f"form6765_{selected_project}.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.error(f"Error: {resp.status_code} -> {resp.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

    with col2:
        if st.button("Download Audit Package ZIP"):
            if not api_key:
                st.error("API key is required.")
            else:
                try:
                    resp = requests.post(
                        f"{backend_url}/audit_package",
                        data={"project_id": selected_project},
                        headers={"X-API-Key": api_key},
                        timeout=120,
                    )
                    if resp.status_code == 200:
                        zip_bytes = resp.content
                        st.download_button(
                            label="Save Audit Package",
                            data=zip_bytes,
                            file_name=f"audit_package_{selected_project}.zip",
                            mime="application/zip",
                        )
                    else:
                        st.error(f"Error: {resp.status_code} -> {resp.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

st.markdown("---")
st.caption("Tip: Start the backend with `uvicorn app.main:app --reload --port 8000` before running Streamlit.")