from pydantic import BaseModel
from typing import Dict, Literal, Optional

Method = Literal["ASC", "REG"]

class CreditInputs(BaseModel):
    year: int
    qre_current: float
    qre_prior_3yrs: Dict[int, float]           # {y-1:..., y-2:..., y-3:...}
    gross_receipts_prior_4yrs: Dict[int, float] = {}  # optional in this lean MVP
    basic_research_payments: float = 0.0
    energy_payments: float = 0.0
    elect_280c: bool = True
    method: Method = "ASC"

class CreditOutputs(BaseModel):
    credit_regular: float
    credit_asc: float
    credit_selected: float
    method_selected: Method
    line_map: Dict[str, float]                 # e.g., "A1": ..., "B41": ...
    explanations: Dict[str, str] = {}

class Form6765Document(BaseModel):
    tax_year: int
    method: Method
    lines: Dict[str, float]
    explanations: Dict[str, str] = {}
    qre_by_category: Optional[Dict[str, float]] = None
