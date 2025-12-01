"""
QRE (Qualified Research Expenses) Auto-Categorization Module (Phase 2.1)

Automatically categorizes expenses into:
- Wages (W2 Box 1) with role-based R&D percentage heuristics
- Supplies
- Cloud Computing Costs
- Contract Research (65% rule)

This is the single biggest value-add for real R&D filings.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# -------------------------
# Constants & Heuristics
# -------------------------

class ExpenseCategory(Enum):
    WAGES = "wages"
    SUPPLIES = "supplies"
    CLOUD_COMPUTING = "cloud_computing"
    CONTRACT_RESEARCH = "contract_research"
    OTHER = "other"

# Role-based R&D percentage heuristics (IRS Section 41 guidelines)
ROLE_RD_PERCENTAGES = {
    "engineer": (0.70, 0.90),      # 70-90% of time on R&D
    "senior engineer": (0.75, 0.95),
    "software engineer": (0.70, 0.90),
    "hardware engineer": (0.65, 0.85),
    "data scientist": (0.65, 0.85),
    "ml engineer": (0.70, 0.90),
    "product engineer": (0.50, 0.75),
    "architect": (0.40, 0.70),
    "analyst": (0.20, 0.40),
    "data analyst": (0.20, 0.40),
    "business analyst": (0.10, 0.30),
    "pm": (0.05, 0.15),
    "product manager": (0.05, 0.15),
    "project manager": (0.05, 0.15),
    "qa": (0.30, 0.60),
    "qa engineer": (0.30, 0.60),
    "devops": (0.20, 0.50),
    "intern": (0.50, 0.80),
}

# Keywords for expense classification
CLOUD_KEYWORDS = {
    "aws", "azure", "gcp", "google cloud", "ec2", "s3", "lambda",
    "cloud", "databricks", "snowflake", "bigquery", "athena",
    "rds", "dynamodb", "redshift", "sagemaker", "openai", "api"
}

SUPPLY_KEYWORDS = {
    "software", "license", "tools", "equipment", "hardware",
    "gpu", "storage", "memory", "cpu", "server", "rack",
    "notebook", "workstation", "monitor", "keyboard", "mouse"
}

CONTRACT_RESEARCH_KEYWORDS = {
    "consultant", "contract", "vendor", "subcontractor", "freelance",
    "outsource", "third party", "external"
}

# -------------------------
# Data Structures
# -------------------------

@dataclass
class ExpenseItem:
    """Individual expense record."""
    id: str
    description: str
    amount: float
    date: str
    employee_id: str = None
    employee_role: str = None
    hours: float = None  # Hours spent (for wage calculation)
    is_eligible: bool = None
    category: ExpenseCategory = None
    confidence: float = 0.0
    rationale: str = ""


@dataclass
class QRECategoryization:
    """QRE categorization result."""
    project_id: str
    total_expenses: float
    wages: float = 0.0
    supplies: float = 0.0
    cloud_computing: float = 0.0
    contract_research: float = 0.0
    other: float = 0.0
    total_qre: float = 0.0
    expense_items: List[ExpenseItem] = None
    notes: str = ""
    timestamp: str = ""


# -------------------------
# Role Heuristics
# -------------------------

def get_rd_percentage_for_role(role: str, conservative: bool = True) -> float:
    """
    Get estimated R&D percentage for a given role.
    If conservative=True, use lower bound. Otherwise, use upper bound.
    """
    role_l = (role or "").lower().strip()
    for keyword, (low, high) in ROLE_RD_PERCENTAGES.items():
        if keyword in role_l:
            return low if conservative else high
    # Default for unknown roles: assume 50% R&D
    return 0.5


def calculate_eligible_wages(
    total_wage: float,
    role: str,
    conservative: bool = True
) -> Tuple[float, float, str]:
    """
    Calculate QRE-eligible wage portion based on role.
    Returns (eligible_wage, percentage_used, rationale)
    """
    rd_pct = get_rd_percentage_for_role(role, conservative)
    eligible_wage = total_wage * rd_pct
    rationale = f"Role '{role}' → {rd_pct*100:.0f}% R&D allocation (conservative={conservative})"
    return eligible_wage, rd_pct, rationale


# -------------------------
# Expense Classification
# -------------------------

def classify_expense(item: ExpenseItem) -> ExpenseItem:
    """
    Classify a single expense into one of the QRE categories.
    Updates item.category and item.confidence in place.
    """
    desc_l = (item.description or "").lower()
    
    # Hard rules for wage items (must have hours or employee_id)
    if item.hours is not None or item.employee_id is not None:
        item.category = ExpenseCategory.WAGES
        item.confidence = 0.95 if item.hours is not None else 0.80
        item.rationale = "Classified as wage expense (has hours or employee tracking)"
        item.is_eligible = True
        return item
    
    # Check for cloud computing
    if any(kw in desc_l for kw in CLOUD_KEYWORDS):
        item.category = ExpenseCategory.CLOUD_COMPUTING
        item.confidence = 0.85
        item.rationale = "Cloud infrastructure/service detected"
        item.is_eligible = True
        return item
    
    # Check for contract research
    if any(kw in desc_l for kw in CONTRACT_RESEARCH_KEYWORDS):
        item.category = ExpenseCategory.CONTRACT_RESEARCH
        item.confidence = 0.80
        item.rationale = "Contract research/outsourcing detected. Subject to 65% limitation."
        item.is_eligible = True
        return item
    
    # Check for supplies
    if any(kw in desc_l for kw in SUPPLY_KEYWORDS):
        item.category = ExpenseCategory.SUPPLIES
        item.confidence = 0.75
        item.rationale = "Software/hardware supplies detected"
        item.is_eligible = True
        return item
    
    # Default: classify as other
    item.category = ExpenseCategory.OTHER
    item.confidence = 0.3
    item.rationale = "Could not match to standard QRE category"
    item.is_eligible = False
    return item


def categorize_expenses(
    items: List[ExpenseItem],
    project_id: str = "unknown",
    conservative: bool = True
) -> QRECategoryization:
    """
    Categorize a list of expenses into QRE buckets.
    
    Args:
        items: List of ExpenseItem objects
        project_id: Project identifier
        conservative: Use conservative R&D % for wages
    
    Returns:
        QRECategoryization with totals and breakdown
    """
    from datetime import datetime
    
    result = QRECategoryization(
        project_id=project_id,
        total_expenses=sum(item.amount for item in items),
        expense_items=[]
    )
    
    for item in items:
        # Classify
        classify_expense(item)
        result.expense_items.append(item)
        
        # Accumulate by category
        if not item.is_eligible:
            result.other += item.amount
        elif item.category == ExpenseCategory.WAGES:
            # For wages, apply R&D percentage
            eligible, _, _ = calculate_eligible_wages(
                item.amount,
                item.employee_role or "unknown",
                conservative
            )
            result.wages += eligible
        elif item.category == ExpenseCategory.CLOUD_COMPUTING:
            result.cloud_computing += item.amount
        elif item.category == ExpenseCategory.SUPPLIES:
            result.supplies += item.amount
        elif item.category == ExpenseCategory.CONTRACT_RESEARCH:
            result.contract_research += item.amount
        else:
            result.other += item.amount
    
    # Calculate total QRE (contract research is subject to 65% limitation)
    contract_limit = result.contract_research * 0.65
    result.total_qre = (
        result.wages
        + result.supplies
        + result.cloud_computing
        + contract_limit
    )
    
    result.timestamp = datetime.utcnow().isoformat() + "Z"
    result.notes = (
        f"Total QRE: ${result.total_qre:,.2f} "
        f"(Wages: ${result.wages:,.2f}, Supplies: ${result.supplies:,.2f}, "
        f"Cloud: ${result.cloud_computing:,.2f}, "
        f"Contract R: ${contract_limit:,.2f} of ${result.contract_research:,.2f})"
    )
    
    return result


# -------------------------
# Summary & Export
# -------------------------

def export_qre_summary(categorization: QRECategoryization) -> Dict[str, Any]:
    """Export categorization as JSON-serializable dict."""
    return {
        "project_id": categorization.project_id,
        "timestamp": categorization.timestamp,
        "total_expenses": categorization.total_expenses,
        "qre_breakdown": {
            "wages": categorization.wages,
            "supplies": categorization.supplies,
            "cloud_computing": categorization.cloud_computing,
            "contract_research_65pct": categorization.contract_research * 0.65,
            "other_ineligible": categorization.other,
        },
        "total_qre": categorization.total_qre,
        "notes": categorization.notes,
    }
