"""
Enhanced Streamlit UI for R&D Tax Credit with Review Workflow.

Features:
- Classification dashboard (existing + recommended_status)
- Review queue (projects needing human review)
- Review panel (view, approve, reject, override)
- Review reports (final decisions with audit trail)
- Export functionality (forms + audit packages + review reports)

Start with: streamlit run streamlit_app_review.py
"""

import streamlit as st
import pandas as pd
import requests
import os
import json
from datetime import datetime

st.set_page_config(page_title="AI R&D Tax Credit Agent - Review Workflow", layout="wide")

# ============================================================================
# Configuration
# ============================================================================

backend_url = st.text_input(
    "Backend URL",
    value=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"),
)
user_id = st.text_input("User ID (for trace)", value="demo-user")
api_key = st.text_input("API Key (X-API-Key)", type="password")

# ============================================================================
# Session State Management
# ============================================================================

if "results_df" not in st.session_state:
    st.session_state["results_df"] = None
if "review_queue" not in st.session_state:
    st.session_state["review_queue"] = None
if "selected_project" not in st.session_state:
    st.session_state["selected_project"] = None


# ============================================================================
# Page Layout
# ============================================================================

st.title("AI R&D Tax Credit Agent - Enhanced Review Workflow")
st.write("Classify R&D projects, manage human reviews, and export audit-ready documents.")

# Create tabs for different workflows
tab_classify, tab_review_queue, tab_review_panel, tab_exports = st.tabs([
    "1️⃣ Classification",
    "2️⃣ Review Queue",
    "3️⃣ Review Panel",
    "4️⃣ Exports"
])


# ============================================================================
# Tab 1: Classification
# ============================================================================

with tab_classify:
    st.header("Step 1: Classify Projects")
    st.write("Upload a CSV to get AI recommendations. Can be re-run without overwriting human decisions.")
    
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key="classify_upload")
    
    if uploaded_file and st.button("Analyze Projects"):
        if not api_key:
            st.error("API key is required.")
        else:
            with st.spinner("Classifying... (this may take a minute)"):
                try:
                    resp = requests.post(
                        f"{backend_url}/classify_rnd",
                        files={"file": uploaded_file},
                        data={"user_id": user_id},
                        headers={"X-API-Key": api_key},
                        timeout=300,
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        if "results" in payload:
                            results_df = pd.DataFrame(payload["results"])
                            st.session_state["results_df"] = results_df
                            st.success(f"✓ Processed {payload.get('count', len(results_df))} projects.")
                    else:
                        st.error(f"Error: {resp.status_code} -> {resp.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")
    
    # Display results
    if st.session_state["results_df"] is not None and not st.session_state["results_df"].empty:
        results_df = st.session_state["results_df"]
        
        st.subheader("Classification Results")
        
        # Create display columns
        display_cols = [
            "project_id",
            "project_name",
            "recommended_status",
            "final_status",
            "confidence",
            "eligible",
        ]
        
        available_cols = [col for col in display_cols if col in results_df.columns]
        st.dataframe(
            results_df[available_cols],
            use_container_width=True,
            height=400,
        )
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            eligible_count = (results_df["eligible"] == True).sum()
            st.metric("Eligible (AI)", eligible_count)
        with col2:
            recommended_eligible = (results_df["recommended_status"] == "RECOMMENDED_ELIGIBLE").sum()
            st.metric("Recommended Eligible", recommended_eligible)
        with col3:
            manual_review = (results_df["recommended_status"] == "MANUAL_REVIEW").sum()
            st.metric("Needs Manual Review", manual_review)
        with col4:
            avg_confidence = results_df["confidence"].mean()
            st.metric("Avg Confidence", f"{avg_confidence:.2%}")


# ============================================================================
# Tab 2: Review Queue
# ============================================================================

with tab_review_queue:
    st.header("Step 2: Review Queue")
    st.write("Projects awaiting human review, sorted by lowest confidence first.")
    
    if st.button("Refresh Review Queue"):
        if not api_key:
            st.error("API key is required.")
        else:
            with st.spinner("Loading review queue..."):
                try:
                    resp = requests.get(
                        f"{backend_url}/reviews/queue",
                        headers={"X-API-Key": api_key},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        queue_data = resp.json()
                        if queue_data.get("queue"):
                            queue_df = pd.DataFrame(queue_data["queue"])
                            st.session_state["review_queue"] = queue_df
                            st.success(f"✓ Found {queue_data['count']} projects needing review.")
                        else:
                            st.info("No projects awaiting review!")
                    else:
                        st.error(f"Error: {resp.status_code}")
                except Exception as e:
                    st.error(f"Request failed: {e}")
    
    # Display queue
    if st.session_state["review_queue"] is not None and not st.session_state["review_queue"].empty:
        queue_df = st.session_state["review_queue"]
        
        st.subheader("Projects Awaiting Review")
        st.dataframe(queue_df, use_container_width=True, height=300)
        
        # Select project from queue
        st.subheader("Select Project for Review")
        project_id = st.selectbox(
            "Choose a project",
            options=queue_df["project_id"].tolist(),
            key="queue_select",
        )
        
        if project_id:
            st.session_state["selected_project"] = project_id
            st.info(f"Project selected: {project_id}")


# ============================================================================
# Tab 3: Review Panel
# ============================================================================

with tab_review_panel:
    st.header("Step 3: Review & Approve/Reject/Override")
    
    # Project selector
    if st.session_state["results_df"] is not None and not st.session_state["results_df"].empty:
        available_projects = st.session_state["results_df"]["project_id"].astype(str).tolist()
        
        selected_project = st.selectbox(
            "Select Project to Review",
            options=available_projects,
            key="review_panel_select",
        )
        
        if selected_project and api_key:
            # Get current review state
            with st.spinner(f"Loading review for {selected_project}..."):
                try:
                    resp = requests.get(
                        f"{backend_url}/reviews/{selected_project}",
                        headers={"X-API-Key": api_key},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        review_state = resp.json()
                        
                        col_left, col_right = st.columns([2, 1])
                        
                        with col_left:
                            st.subheader(f"Project: {selected_project}")
                            
                            # Get classification data
                            if st.session_state["results_df"] is not None:
                                proj_data = st.session_state["results_df"][
                                    st.session_state["results_df"]["project_id"] == selected_project
                                ]
                                if not proj_data.empty:
                                    proj_row = proj_data.iloc[0]
                                    
                                    st.write(f"**Name**: {proj_row.get('project_name', 'N/A')}")
                                    st.write(f"**Rationale**: {proj_row.get('rationale', 'N/A')}")
                                    st.write(f"**AI Recommendation**: {proj_row.get('recommended_status', 'UNKNOWN')}")
                                    st.write(f"**Confidence**: {proj_row.get('confidence', 0):.1%}")
                                    st.write(f"**Trace**: {proj_row.get('trace_path', 'N/A')}")
                        
                        with col_right:
                            st.subheader("Current Status")
                            current_status = review_state.get("current_status", "UNREVIEWED")
                            st.metric("Status", current_status)
                        
                        # Review history
                        if review_state.get("history"):
                            st.subheader("Review History")
                            for i, review in enumerate(reversed(review_state["history"])):
                                with st.expander(f"Review {i+1}: {review['status']}"):
                                    st.write(f"**Reviewer**: {review['reviewer_name']}")
                                    st.write(f"**Role**: {review['reviewer_role']}")
                                    st.write(f"**Reason**: {review['reason']}")
                                    st.write(f"**Timestamp**: {review['timestamp']}")
                        
                        # Action form
                        st.subheader("Submit Review Action")
                        
                        with st.form(f"review_form_{selected_project}"):
                            action_status = st.selectbox(
                                "Decision",
                                options=[
                                    "APPROVED",
                                    "REJECTED",
                                    "OVERRIDDEN",
                                ]
                            )
                            
                            reviewer_name = st.text_input("Your Name")
                            reviewer_role = st.selectbox(
                                "Your Role",
                                options=[
                                    "ANALYST",
                                    "REVIEWER",
                                    "TAX_MANAGER",
                                    "DIRECTOR",
                                    "PARTNER",
                                    "ADMIN",
                                ]
                            )
                            reason = st.text_area(
                                "Reason (min 20 characters)",
                                min_chars=20,
                                height=100,
                            )
                            
                            submitted = st.form_submit_button("Submit Review")
                            
                            if submitted:
                                if not api_key:
                                    st.error("API key required")
                                elif not reviewer_name:
                                    st.error("Please enter your name")
                                elif len(reason) < 20:
                                    st.error("Reason must be at least 20 characters")
                                else:
                                    with st.spinner("Submitting review..."):
                                        try:
                                            resp = requests.post(
                                                f"{backend_url}/reviews/{selected_project}/action",
                                                json={
                                                    "status": action_status,
                                                    "reviewer_name": reviewer_name,
                                                    "reviewer_role": reviewer_role,
                                                    "reason": reason,
                                                },
                                                headers={"X-API-Key": api_key},
                                                timeout=30,
                                            )
                                            if resp.status_code == 200:
                                                st.success(f"✓ Review submitted: {action_status}")
                                                st.rerun()
                                            else:
                                                st.error(f"Error: {resp.status_code} -> {resp.json().get('detail', 'Unknown error')}")
                                        except Exception as e:
                                            st.error(f"Request failed: {e}")
                    
                    else:
                        st.error(f"Error loading review: {resp.status_code}")
                except Exception as e:
                    st.error(f"Request failed: {e}")


# ============================================================================
# Tab 4: Exports
# ============================================================================

with tab_exports:
    st.header("Step 4: Export Documents")
    st.write("Generate audit-ready documents: Form 6765, audit package, and review reports.")
    
    if st.session_state["results_df"] is not None and not st.session_state["results_df"].empty:
        results_df = st.session_state["results_df"]
        project_ids = results_df["project_id"].astype(str).tolist()
        
        selected_project = st.selectbox("Select Project for Export", project_ids, key="export_select")
        
        if selected_project and api_key:
            with st.expander("Form 6765 Configuration", expanded=False):
                cfg_col1, cfg_col2 = st.columns(2)

                with cfg_col1:
                    tax_year = st.number_input(
                        "Tax Year",
                        min_value=1990,
                        max_value=2100,
                        value=datetime.utcnow().year,
                        step=1,
                        key="cfg_tax_year",
                    )
                    name_on_return = st.text_input(
                        "Name on Return",
                        value="Sample Taxpayer Inc.",
                        key="cfg_name_on_return",
                    )
                    identifying_number = st.text_input(
                        "Identifying Number",
                        value="00-0000000",
                        key="cfg_identifying_number",
                    )
                    ruleset_version = st.text_input(
                        "Ruleset Version",
                        value="2024.1",
                        key="cfg_ruleset_version",
                    )
                    prompt_version = st.text_input(
                        "Prompt Version (optional)",
                        value="",
                        key="cfg_prompt_version",
                    )
                    created_by = st.text_input(
                        "Created By",
                        value=user_id or "review-analyst",
                        key="cfg_created_by",
                    )
                    lock_reason = st.text_input(
                        "Lock Reason",
                        value=f"Initial lock for {selected_project}",
                        key="cfg_lock_reason",
                    )
                    override_reason = st.text_area(
                        "Override Reason (30+ chars, optional)",
                        value="",
                        help="Provide when regenerating a locked form",
                        key="cfg_override_reason",
                    )
                    override_role = st.selectbox(
                        "Override Role (if overriding)",
                        options=["", "ADMIN", "PARTNER", "DIRECTOR"],
                        key="cfg_override_role",
                    )

                with cfg_col2:
                    qre_wages = st.number_input(
                        "QRE Wages",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_qre_wages",
                    )
                    qre_supplies = st.number_input(
                        "QRE Supplies",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_qre_supplies",
                    )
                    qre_computers = st.number_input(
                        "QRE Computers",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_qre_computers",
                    )
                    qre_contract = st.number_input(
                        "Contract Research (gross)",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_qre_contract",
                    )
                    contract_pct = st.slider(
                        "Contract Applicable %",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.65,
                        step=0.05,
                        key="cfg_contract_pct",
                    )
                    credit_method = st.selectbox(
                        "Credit Method",
                        options=["ASC", "REGULAR"],
                        key="cfg_credit_method",
                    )
                    fixed_base_percentage = st.number_input(
                        "Fixed Base Percentage (REGULAR only)",
                        min_value=0.0,
                        max_value=0.16,
                        value=0.0,
                        step=0.01,
                        key="cfg_fixed_base",
                    )
                    avg_receipts = st.number_input(
                        "Avg Annual Gross Receipts (REGULAR only)",
                        min_value=0.0,
                        value=0.0,
                        step=10000.0,
                        key="cfg_avg_receipts",
                    )
                    prior_qre = st.number_input(
                        "Prior 3-Year QRE Total",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_prior_qre",
                    )
                    section_280c_choice = st.selectbox(
                        "Section 280C Choice",
                        options=["FULL", "REDUCED"],
                        key="cfg_280c",
                    )
                    is_qsb = st.checkbox(
                        "Payroll Tax Election (QSB)?",
                        value=False,
                        key="cfg_is_qsb",
                    )
                    payroll_tax_credit_elected = st.number_input(
                        "Payroll Tax Credit Elected",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_payroll_credit",
                    )
                    general_business_credit_carryforward = st.number_input(
                        "General Business Credit Carryforward",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_gbc_carryforward",
                    )
                    form_8932_overlap = st.number_input(
                        "Form 8932 Overlap Wages Credit",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_form8932",
                    )
                    pass_through_credit = st.number_input(
                        "Pass-through Credit",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_pass_through",
                    )
                    energy_amount = st.number_input(
                        "Energy Consortium Amount",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_energy_amount",
                    )
                    basic_research = st.number_input(
                        "Basic Research Payments",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_basic_research",
                    )
                    base_period_amount = st.number_input(
                        "Qualified Org Base Period Amount",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                        key="cfg_base_period",
                    )

            col1, col2, col3 = st.columns(3)

            # Form 6765
            with col1:
                if st.button("📄 Generate Form 6765 Package"):
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

                        with st.spinner("Generating enterprise form package..."):
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
                                                label="💾 Save Form 6765 PDF",
                                                data=pdf_resp.content,
                                                file_name=f"form6765_{form_version_id}.pdf",
                                                mime="application/pdf",
                                                key=f"download_form_{selected_project}",
                                            )
                                        else:
                                            st.warning("Form generated but PDF unavailable.")
                                    else:
                                        st.success("Form generated.")
                                else:
                                    st.error(f"Error: {resp.status_code} -> {resp.text}")
                            except Exception as e:
                                st.error(f"Failed: {e}")
            
            # Audit Package
            with col2:
                if st.button("📦 Download Audit Package ZIP"):
                    with st.spinner("Generating audit package..."):
                        try:
                            resp = requests.post(
                                f"{backend_url}/audit_package",
                                data={"project_id": selected_project},
                                headers={"X-API-Key": api_key},
                                timeout=120,
                            )
                            if resp.status_code == 200:
                                st.download_button(
                                    label="💾 Save Audit Package",
                                    data=resp.content,
                                    file_name=f"audit_package_{selected_project}.zip",
                                    mime="application/zip",
                                    key=f"download_audit_{selected_project}",
                                )
                            else:
                                st.error(f"Error: {resp.status_code}")
                        except Exception as e:
                            st.error(f"Failed: {e}")
            
            # Review Report
            with col3:
                if st.button("📋 View Review Report"):
                    with st.spinner("Loading review report..."):
                        try:
                            resp = requests.get(
                                f"{backend_url}/reviews/{selected_project}/report",
                                headers={"X-API-Key": api_key},
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                report = resp.json()
                                st.json(report)
                                
                                # Option to download as JSON
                                st.download_button(
                                    label="💾 Save Report as JSON",
                                    data=json.dumps(report, indent=2, default=str),
                                    file_name=f"review_report_{selected_project}.json",
                                    mime="application/json",
                                )
                            else:
                                st.error(f"Error: {resp.status_code}")
                        except Exception as e:
                            st.error(f"Failed: {e}")


# ============================================================================
# Footer
# ============================================================================

st.markdown("---")
st.caption("💡 Tip: Start the backend with `uvicorn app.main:app --reload` before using this app.")
st.caption("🔐 Ensure X-API-Key is configured in your .env file with appropriate roles.")
