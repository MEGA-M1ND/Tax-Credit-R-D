from app.contracts.form_6765 import CreditInputs, CreditOutputs, Method

def _round2(x: float) -> float:
    return float(round(x, 2))

def calc_regular(inputs: CreditInputs) -> tuple[float, dict]:
    """
    Lean Regular method placeholder:
    credit = 20% * max(QRE_current - base, 0)
    For MVP, base ~ 50% * avg(prior_3yrs_QRE)
    NOTE: Replace with fixed-base/startup base later.
    """
    notes = {}
    qre = inputs.qre_current
    avg_prior = (sum(inputs.qre_prior_3yrs.values()) / 3.0) if inputs.qre_prior_3yrs else 0.0
    base = 0.5 * avg_prior
    excess = max(qre - base, 0.0)
    credit = 0.20 * excess
    notes.update(dict(qre=qre, avg_prior=avg_prior, base=base, excess_regular=excess))
    return _round2(credit), notes

def calc_asc(inputs: CreditInputs) -> tuple[float, dict]:
    """
    ASC method:
    credit = 14% * max(QRE_current - 50% * avg(prior_3yrs_QRE), 0)
    """
    notes = {}
    qre = inputs.qre_current
    avg_prior = (sum(inputs.qre_prior_3yrs.values()) / 3.0) if inputs.qre_prior_3yrs else 0.0
    threshold = 0.5 * avg_prior
    excess = max(qre - threshold, 0.0)
    credit = 0.14 * excess
    notes.update(dict(qre=qre, avg_prior=avg_prior, asc_threshold=threshold, excess_asc=excess))
    return _round2(credit), notes

def apply_280c_reduction(amount: float, rate: float = 0.79) -> float:
    # Simple proxy for MVP; make configurable later.
    return _round2(amount * rate)

def compute_credit(inputs: CreditInputs) -> CreditOutputs:
    reg, nreg = calc_regular(inputs)
    asc, nasc = calc_asc(inputs)

    method_selected: Method = "ASC" if asc >= reg else "REG"
    selected = asc if method_selected == "ASC" else reg

    if inputs.elect_280c:
        reg = apply_280c_reduction(reg)
        asc = apply_280c_reduction(asc)
        selected = apply_280c_reduction(selected)

    line_map = {
        "A1": _round2(inputs.qre_current),                            # helper for demo
        "A2": _round2(sum(inputs.qre_prior_3yrs.values() or [0.0])),  # helper
        "A3": reg,            # placeholder: regular method result
        "B41": asc,           # ASC method result
        "B44": selected,      # chosen (demo)
    }
    explanations = {
        "regular.notes": str(nreg),
        "asc.notes": str(nasc),
        "280C.applied": str(inputs.elect_280c),
        "method_selected": method_selected
    }

    return CreditOutputs(
        credit_regular=reg,
        credit_asc=asc,
        credit_selected=selected,
        method_selected=method_selected,
        line_map=line_map,
        explanations=explanations
    )
