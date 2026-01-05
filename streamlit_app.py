import streamlit as st
import pandas as pd
import requests
import os
from datetime import datetime

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

    st.markdown("#### Form 6765 Configuration")
    config_col1, config_col2 = st.columns(2)

    with config_col1:
        tax_year = st.number_input(
            "Tax Year",
            min_value=1990,
            max_value=2100,
            value=datetime.utcnow().year,
            step=1,
        )
        name_on_return = st.text_input("Name on Return", value="Sample Taxpayer Inc.")
        identifying_number = st.text_input("Identifying Number", value="00-0000000")
        ruleset_version = st.text_input("Ruleset Version", value="2024.1")
        prompt_version = st.text_input("Prompt Version (optional)", value="")
        created_by = st.text_input("Created By", value=user_id or "streamlit-user")
        lock_reason = st.text_input(
            "Lock Reason",
            value=f"Initial form generation for {selected_project}",
        )
        override_reason = st.text_area(
            "Override Reason (30+ chars, optional)",
            value="",
            help="Required only when regenerating a locked form",
        )
        override_role = st.selectbox(
            "Override Role (if overriding)",
            options=["", "ADMIN", "PARTNER", "DIRECTOR"],
        )

    with config_col2:
        qre_wages = st.number_input("QRE Wages", min_value=0.0, value=0.0, step=1000.0)
        qre_supplies = st.number_input("QRE Supplies", min_value=0.0, value=0.0, step=1000.0)
        qre_computers = st.number_input("QRE Computers", min_value=0.0, value=0.0, step=1000.0)
        qre_contract = st.number_input("Contract Research (gross)", min_value=0.0, value=0.0, step=1000.0)
        contract_pct = st.slider("Contract Applicable %", min_value=0.0, max_value=1.0, value=0.65, step=0.05)
        credit_method = st.selectbox("Credit Method", options=["ASC", "REGULAR"])
        fixed_base_percentage = st.number_input(
            "Fixed Base Percentage (REGULAR only)",
            min_value=0.0,
            max_value=0.16,
            value=0.0,
            step=0.01,
        )
        avg_receipts = st.number_input(
            "Avg Annual Gross Receipts (REGULAR only)",
            min_value=0.0,
            value=0.0,
            step=10000.0,
        )
        prior_qre = st.number_input("Prior 3-Year QRE Total", min_value=0.0, value=0.0, step=1000.0)
        section_280c_choice = st.selectbox("Section 280C Choice", options=["FULL", "REDUCED"])
        is_qsb = st.checkbox("Payroll Tax Election (QSB)?", value=False)
        payroll_tax_credit_elected = st.number_input(
            "Payroll Tax Credit Elected",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )
        general_business_credit_carryforward = st.number_input(
            "General Business Credit Carryforward",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )
        form_8932_overlap = st.number_input(
            "Form 8932 Overlap Wages Credit",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )
        pass_through_credit = st.number_input(
            "Pass-through Credit",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )
        energy_amount = st.number_input("Energy Consortium Amount", min_value=0.0, value=0.0, step=1000.0)
        basic_research = st.number_input("Basic Research Payments", min_value=0.0, value=0.0, step=1000.0)
        base_period_amount = st.number_input(
            "Qualified Org Base Period Amount",
            min_value=0.0,
            value=0.0,
            step=1000.0,
        )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Generate Form 6765 Package"):
            if not api_key:
                st.error("API key is required.")
            else:
                if override_reason.strip() and len(override_reason.strip()) < 30:
                    st.error("Override reason must be at least 30 characters.")
                elif override_reason.strip() and not override_role:
                    st.error("Select an override role when providing an override reason.")
                elif credit_method == "REGULAR" and (fixed_base_percentage <= 0 or avg_receipts <= 0):
                    st.error("Fixed base % and average gross receipts are required for REGULAR credit.")
                else:
                    inputs_payload = {
                        "qre_wages": qre_wages,
                        "qre_supplies": qre_supplies,
                        "qre_computers": qre_computers,
                        "qre_contract_research_gross": qre_contract,
                        "contract_applicable_pct": contract_pct,
                        "fixed_base_percentage": fixed_base_percentage if credit_method == "REGULAR" else None,
                        "avg_annual_gross_receipts": avg_receipts if credit_method == "REGULAR" else None,
                        "prior_3_year_qre_total": prior_qre,
                        "energy_consortia_amount": energy_amount,
                        "basic_research_payments": basic_research,
                        "qualified_org_base_period_amount": base_period_amount,
                        "form_8932_overlap_wages_credit": form_8932_overlap,
                        "pass_through_credit": pass_through_credit,
                        "is_qsb_payroll_election": is_qsb,
                        "payroll_tax_credit_elected": payroll_tax_credit_elected,
                        "general_business_credit_carryforward": general_business_credit_carryforward,
                        "credit_method": credit_method,
                        "section_280c_choice": section_280c_choice,
                    }

                    payload = {
                        "header": {
                            "tax_year": int(tax_year),
                            "name_on_return": name_on_return,
                            "identifying_number": identifying_number,
                        },
                        "inputs": inputs_payload,
                        "project_ids": [selected_project],
                        "ruleset_version": ruleset_version,
                        "created_by": created_by,
                        "reviewer_rollup": {},
                        "prompt_version": prompt_version or None,
                        "lock_reason": lock_reason,
                        "override_reason": override_reason or None,
                        "save_pdf": True,
                    }

                    headers = {"X-API-Key": api_key}
                    if override_reason.strip() and override_role:
                        headers["X-Role"] = override_role

                    with st.spinner("Generating and locking Form 6765..."):
                        try:
                            resp = requests.post(
                                f"{backend_url}/form6765/generate",
                                json=payload,
                                headers=headers,
                                timeout=180,
                            )
                            if resp.status_code == 200:
                                result = resp.json()
                                form_version = result.get("form_version", {})
                                form_version_id = form_version.get("form_version_id")
                                approved_projects = result.get("snapshot", {}).get("approved_project_ids", [])
                                if approved_projects:
                                    st.info("Approved projects frozen: " + ", ".join(approved_projects))
                                if form_version_id:
                                    pdf_resp = requests.get(
                                        f"{backend_url}/form6765/form/{form_version_id}/pdf",
                                        headers={"X-API-Key": api_key},
                                        timeout=120,
                                    )
                                    if pdf_resp.status_code == 200:
                                        st.download_button(
                                            label="Save Form 6765 PDF",
                                            data=pdf_resp.content,
                                            file_name=f"form6765_{form_version_id}.pdf",
                                            mime="application/pdf",
                                        )
                                    else:
                                        st.warning("Form generated but PDF unavailable.")
                                else:
                                    st.success("Form generated.")
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