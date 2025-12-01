# app/agentic_pipeline.py

from typing import List, Dict, Any
from typing_extensions import TypedDict
from datetime import datetime
import os
import json
import re
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from openai import OpenAI
from openai import APIConnectionError
import time


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set – required for agentic pipeline demo.")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
client = OpenAI()


def _extract_text_from_message_content(content: Any) -> str:
    """
    Normalize OpenAI ChatCompletion message.content to a plain string.

    Handles:
    - Plain strings
    - List[dict] with keys like {"type": "text", "text": "..."}
    - List[dict] with {"type": "output_text", "text": {"value": "..."}}
    - Objects with .text or .value attributes (future-proofing)
    """
    # Simple case: it's already a string
    if isinstance(content, str):
        return content

    parts: List[str] = []

    # Newer APIs: content is a list of parts
    if isinstance(content, list):
        for part in content:
            # Common pattern: {"type": "text", "text": "..." }
            if isinstance(part, dict):
                if "text" in part and isinstance(part["text"], str):
                    parts.append(part["text"])
                elif "text" in part and isinstance(part["text"], dict) and "value" in part["text"]:
                    # e.g. {"type": "output_text", "text": {"value": "..."}}
                    parts.append(str(part["text"]["value"]))
                else:
                    # Fallback: stringify
                    parts.append(str(part))
            else:
                # Object with .text or .value
                t = getattr(part, "text", None)
                if t is not None:
                    if hasattr(t, "value"):
                        parts.append(str(t.value))
                    else:
                        parts.append(str(t))
                else:
                    v = getattr(part, "value", None)
                    if v is not None:
                        parts.append(str(v))
                    else:
                        parts.append(str(part))
        return "\n".join(parts)

    # Last resort: stringify whatever it is
    return str(content)


def call_llm(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """
    Thin wrapper around OpenAI Chat Completions that:
    - Handles gpt-5 parameter constraints
    - Normalizes response content into a plain string
    - Raises a clear error if content is unexpectedly empty
    """
    model = model or OPENAI_MODEL

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Base parameters
    completion_params: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    # gpt-5 has stricter parameter rules:
    # - No temperature override (must use default)
    # - No "max_tokens"; use max_completion_tokens instead if needed
    if not model.lower().startswith("gpt-5"):
        completion_params["temperature"] = 1
        completion_params["max_tokens"] = 800

    resp = client.chat.completions.create(
    **completion_params,
    timeout=60  # add this
    )


    message = resp.choices[0].message
    raw_content = message.content
    text = _extract_text_from_message_content(raw_content)
    content_stripped = (text or "").strip()

    if not content_stripped:
        # Helpful debug info
        raise RuntimeError(
            f"LLM returned empty content. "
            f"Model={model}, system_prompt_len={len(system_prompt)}, user_prompt_len={len(user_prompt)}, "
            f"raw_content={repr(raw_content)}"
        )

    return content_stripped


class RDTaxState(TypedDict, total=False):
    project: Dict[str, Any]
    raw_expenses: List[Dict[str, Any]]
    eligibility: Dict[str, Any]
    expense_analysis: Dict[str, Any]
    narrative: str
    evidence_log: List[Dict[str, Any]]
    summary: Dict[str, Any]


def _append_evidence(state: RDTaxState, agent_name: str, action: str, details: Dict[str, Any]) -> None:
    log = state.get("evidence_log") or []
    log.append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": agent_name,
            "action": action,
            "details": details,
        }
    )
    state["evidence_log"] = log


# -------------------------
# EligibilityAgent
# -------------------------
def eligibility_agent(state: RDTaxState) -> RDTaxState:
    project = state["project"]

    system_prompt = """
You are an IRS R&D Tax Credit eligibility analyst.
Evaluate the project against the Four-Part Test:
1. Permitted Purpose
2. Technological in Nature
3. Elimination of Uncertainty
4. Process of Experimentation

Return STRICTLY VALID JSON ONLY (no prose, no markdown, no comments) with this schema:

{
  "eligible": true/false,
  "reasoning": ["bullet 1", "bullet 2", "..."],
  "failed_criteria": ["Permitted Purpose", "Technological in Nature"],
  "recommended_evidence": [
    "Project charter...",
    "Experiment plans...",
    "Ablation studies...",
    "..."
  ]
}
"""
    user_prompt = f"Project metadata:\n{project}"

    result_text = call_llm(system_prompt, user_prompt)

    # Try to parse JSON; fall back to raw text if parsing fails
    try:
        # Sometimes models wrap JSON with extra text – extract first {...}
        match = re.search(r"\{.*\}", result_text, re.S)
        json_str = match.group(0) if match else result_text

        parsed = json.loads(json_str)

        eligibility = {
            "eligible": bool(parsed.get("eligible", False)),
            "reasoning": parsed.get("reasoning", []),
            "failed_criteria": parsed.get("failed_criteria", []),
            "recommended_evidence": parsed.get("recommended_evidence", []),
        }
    except Exception as e:
        # Fallback – keep what we got so you can debug
        eligibility = {
            "parse_error": str(e),
            "raw_text": result_text,
        }

    _append_evidence(
        state,
        agent_name="EligibilityAgent",
        action="evaluated_four_part_test",
        details=eligibility,
    )

    state["eligibility"] = eligibility
    return state



# -------------------------
# ExpenseAgent
# -------------------------
def expense_agent(state: RDTaxState) -> RDTaxState:
    expenses = state["raw_expenses"]

    system_prompt = """
You are an assistant classifying expenses under IRS Section 41 QRE rules.

For each expense row, you MUST produce:
- description: string
- amount: number
- category: one of ["WAGES","CONTRACTOR","SUPPLIES","CLOUD","OTHER"]
- eligible: true/false
- qre_amount: number actually counted as QRE (e.g., 65% for contract research)
- short_reason: brief explanation of why/why not.

You MUST return a SINGLE JSON object ONLY, with this schema:

{
  "rows": [
    {
      "description": "...",
      "amount": 54000.0,
      "category": "WAGES",
      "eligible": true,
      "qre_amount": 54000.0,
      "short_reason": "Employee wages for qualified research activities..."
    },
    ...
  ],
  "totals": {
    "qre_total": 117700.0,
    "non_qre_total": 20000.0
  }
}

No extra text, no markdown, no comments – JSON ONLY.
"""
    user_prompt = f"Expenses JSON:\n{expenses}"

    result_text = call_llm(system_prompt, user_prompt)

    # Parse JSON; fall back to raw text if parsing fails
    try:
        match = re.search(r"\{.*\}", result_text, re.S)
        json_str = match.group(0) if match else result_text

        parsed = json.loads(json_str)

        rows = parsed.get("rows", [])
        totals = parsed.get("totals", {})

        expense_analysis = {
            "rows": rows,
            "totals": {
                "qre_total": totals.get("qre_total"),
                "non_qre_total": totals.get("non_qre_total"),
            },
        }
    except Exception as e:
        expense_analysis = {
            "parse_error": str(e),
            "raw_text": result_text,
        }

    _append_evidence(
        state,
        agent_name="ExpenseAgent",
        action="classified_expenses",
        details=expense_analysis,
    )

    state["expense_analysis"] = expense_analysis
    return state

# -------------------------
# NarrativeAgent
# -------------------------
def narrative_agent(state: RDTaxState) -> RDTaxState:
    project = state["project"]
    eligibility = state.get("eligibility", {})
    expense_analysis = state.get("expense_analysis", {})

    system_prompt = """
You are a technical writer generating IRS R&D Tax Credit narratives.
Write a structured, audit-ready narrative with headings:

1. Project Overview
2. Technological Uncertainty
3. Technological Basis
4. Process of Experimentation
5. R&D Activities and Personnel
6. Summary of Qualified Research Expenses

Use clear, professional language suitable for IRS review.
"""
    user_prompt = f"""
Write a detailed IRS R&D tax credit narrative using these fields:

Project Name: {project['name']}
Description: {project['description']}
Tech Domain: {project['tech_domain']}

Eligibility (summary):
Eligible: {eligibility.get('eligible')}
Key Reasoning: {eligibility.get('reasoning', [])}

Expenses Summary:
QRE Total: {expense_analysis['totals']['qre_total']}
Non-QRE Total: {expense_analysis['totals']['non_qre_total']}
"""


    narrative = call_llm(system_prompt, user_prompt, model="gpt-4.1")

    _append_evidence(
        state,
        agent_name="NarrativeAgent",
        action="generated_narrative",
        details={"narrative_preview": narrative[:400]},
    )

    state["narrative"] = narrative
    return state


# -------------------------
# EvidenceAgent (finalize summary)
# -------------------------
def evidence_agent(state: RDTaxState) -> RDTaxState:
    summary = {
        "project": state.get("project"),
        "eligibility": state.get("eligibility"),
        "expense_analysis": state.get("expense_analysis"),
        "narrative": state.get("narrative"),
        "evidence_log": state.get("evidence_log", []),
    }

    _append_evidence(
        state,
        agent_name="EvidenceAgent",
        action="finalized_summary",
        details={"keys": list(summary.keys())},
    )

    state["summary"] = summary
    return state


# -------------------------
# Graph builder
# -------------------------
def build_graph():
    workflow = StateGraph(RDTaxState)

    workflow.add_node("eligibility", eligibility_agent)
    workflow.add_node("expense", expense_agent)
    workflow.add_node("narrative", narrative_agent)
    workflow.add_node("evidence", evidence_agent)

    workflow.set_entry_point("eligibility")

    workflow.add_edge("eligibility", "expense")
    workflow.add_edge("expense", "narrative")
    workflow.add_edge("narrative", "evidence")
    workflow.add_edge("evidence", END)

    return workflow.compile()
