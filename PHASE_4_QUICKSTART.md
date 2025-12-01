# Phase 4: Quick Start Guide

## TL;DR

Three new NLP features analyze projects with intelligent decomposition, uncertainty detection, and evidence extraction:

```python
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp

record = ProjectRecord(
    project_id="PROJ-001",
    project_name="My Project",
    description="Project description...",
)

result = analyze_project_with_advanced_nlp(record)

# Get results
print(result["classification"]["eligible"])           # Basic eligibility
print(result["advanced_nlp"]["decomposition"])       # Component breakdown
print(result["advanced_nlp"]["uncertainty"])         # Uncertainty score
print(result["advanced_nlp"]["evidence"])            # Evidence phrases
```

---

## Features at a Glance

### 4.1 Project Decomposition
**What**: Break projects into components (Research, Infrastructure, Maintenance, Support, Business)  
**Why**: Many projects are mixed - some eligible, some not  
**Output**: Percentage breakdown showing which components are research-eligible

```python
from app.advanced_nlp import ProjectDecomposer

decomposer = ProjectDecomposer()
result = decomposer.decompose_project(
    project_id="PROJ-001",
    project_name="Navigation System",
    project_description="We built ML pathfinding...",
)

print(f"{result.eligible_percentage*100:.0f}% eligible")
for component in result.components:
    print(f"  {component.name}: {component.component_type.value}")
```

**Output**:
```
82% eligible
  ML Pathfinding: research
  Dashboard UI: infrastructure
  Data Migration: maintenance
```

---

### 4.2 Uncertainty Detector
**What**: Find evidence of technical uncertainty (IRS §41 requirement)  
**Why**: Auditors need proof of genuine technical unknowns  
**Output**: Score 0.0-1.0 showing strength of uncertainty evidence

```python
from app.advanced_nlp import UncertaintyDetector

detector = UncertaintyDetector()
result = detector.detect_uncertainties("Project description...")

print(f"Uncertainty Score: {result.overall_uncertainty_score:.2f}")
print(f"Technical Unknowns: {result.has_technical_unknowns}")
print(f"Experiments: {result.has_experiments}")
print(f"Benchmarks: {result.has_benchmarks}")
print(f"Failures: {result.has_failures}")
print(f"New Methods: {result.has_new_methods}")
```

**Output**:
```
Uncertainty Score: 0.85
Technical Unknowns: True
Experiments: True
Benchmarks: True
Failures: True
New Methods: True
```

---

### 4.3 Experimentation Evidence Extractor
**What**: Extract specific phrases showing systematic experimentation  
**Why**: Auditors need concrete examples for defense  
**Output**: Categorized evidence phrases with quotes and context

```python
from app.advanced_nlp import ExperimentationExtractor

extractor = ExperimentationExtractor()
result = extractor.extract_evidence(
    project_id="PROJ-001",
    project_description="Project description..."
)

print(f"Evidence Strength: {result.evidence_strength}")
print(f"Total Phrases: {result.total_phrases_found}")

for phrase in result.architecture_comparisons:
    print(f"  Quote: {phrase.quote}")
    print(f"  Context: {phrase.context}")
```

**Output**:
```
Evidence Strength: strong
Total Phrases: 12

Architecture Comparisons:
  Quote: multiple architectures: CNN, GNN, and hybrid
  Context: We prototyped multiple architectures...

Parameter Optimizations:
  Quote: optimized parameters through grid search
  Context: We optimized parameters through grid...
```

---

## Integration Examples

### Example 1: Full Analysis
```python
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp

record = ProjectRecord(
    project_id="PROJ-NAV-001",
    project_name="Navigation System",
    description="We developed ML pathfinding...",
)

# Run all three features
result = analyze_project_with_advanced_nlp(record)

# Phase 1-3: Basic eligibility
if result["classification"]["eligible"]:
    print("✓ Eligible")
    
    # Phase 4: Component breakdown
    decomp = result["advanced_nlp"]["decomposition"]
    print(f"Components: {decomp['total_components']}")
    print(f"Eligible: {decomp['eligible_percentage']*100:.0f}%")
    
    # Phase 4: Uncertainty evidence
    uncertainty = result["advanced_nlp"]["uncertainty"]
    print(f"Uncertainty: {uncertainty['overall_uncertainty_score']:.2f}")
    
    # Phase 4: Evidence for audit defense
    evidence = result["advanced_nlp"]["evidence"]
    print(f"Evidence Phrases: {evidence['total_phrases_found']}")
```

### Example 2: Only Decomposition
```python
# Get component breakdown only
result = analyze_project_with_advanced_nlp(
    record=record,
    enable_decomposition=True,
    enable_uncertainty=False,
    enable_evidence=False,
)

decomp = result["advanced_nlp"]["decomposition"]
```

### Example 3: Selective Features
```python
# Disable expensive features, enable fast ones
result = analyze_project_with_advanced_nlp(
    record=record,
    enable_decomposition=True,      # ✓ Fast (keyword-based)
    enable_uncertainty=True,        # ✓ Fast (regex-based)
    enable_evidence=True,           # ✓ Fast (regex-based)
)
```

### Example 4: Use in Form Generation
```python
from app.qre_categorization import categorize_expenses
from app.form_6765_generator import Form6765Generator

# Get decomposition
result = analyze_project_with_advanced_nlp(record)
eligible_pct = result["advanced_nlp"]["decomposition"]["eligible_percentage"]

# Calculate eligible wages
expenses = [...]  # Some expenses
categorized = categorize_expenses(expenses)
eligible_qre = categorized.eligible_amount * eligible_pct

# Generate form
form_gen = Form6765Generator()
form = form_gen.generate(
    company_name="Acme Inc",
    tax_year=2024,
    qualified_research_expenses=eligible_qre,
    research_wages=eligible_qre * 0.6,
    supplies_cost=eligible_qre * 0.3,
)

form.to_pdf("form_6765.pdf")
```

### Example 5: Use in Audit Defense
```python
from app.audit_defense_pack import AuditDefenseGenerator

# Get evidence
result = analyze_project_with_advanced_nlp(record)
evidence = result["advanced_nlp"]["evidence"]
uncertainty = result["advanced_nlp"]["uncertainty"]

# Generate defense pack with evidence
audit_gen = AuditDefenseGenerator()
audit = audit_gen.generate(
    project_id=record.project_id,
    description=f"""
    Project: {record.project_name}
    
    Uncertainty Evidence (IRS §41 Part 2):
    {uncertainty['rationale']}
    
    Experimentation Phrases:
    {evidence['audit_ready_summary']}
    """,
    team_members=["Alice Engineer", "Bob Data Scientist"],
    expenses=[],
)

audit.to_markdown("audit_defense.md")
```

---

## Output Structure

### Result Dictionary
```python
result = {
    "classification": {
        "project_id": "...",
        "eligible": True|False,
        "confidence": 0.0-1.0,
        "rationale": "...",
        "region": "US-IRS-Section-41",
    },
    "trace": {
        "user_id": "...",
        "project_id": "...",
        "steps": [...],  # Detailed decision trail
    },
    "advanced_nlp": {
        "decomposition": {
            "project_id": "...",
            "total_components": 5,
            "components": [
                {
                    "name": "ML Pathfinding",
                    "component_type": "research",
                    "eligible": True,
                    "estimated_percentage": 60.0,
                    "confidence": 0.75,
                    # ...
                },
                # ...
            ],
            "eligible_percentage": 0.82,  # 82%
            "overall_eligibility": "eligible",
            # ...
        },
        "uncertainty": {
            "project_id": "...",
            "has_technical_unknowns": True,
            "has_experiments": True,
            "has_benchmarks": True,
            "has_failures": True,
            "has_new_methods": True,
            "overall_uncertainty_score": 0.80,
            "indicators": [
                {
                    "indicator_type": "experiment",
                    "description": "Detected: tested",
                    "confidence": 0.7,
                    "evidence_phrases": ["tested"],
                },
                # ...
            ],
            "missing_evidence": [],
            "rationale": "...",
        },
        "evidence": {
            "project_id": "...",
            "total_phrases_found": 12,
            "architecture_comparisons": [
                {
                    "phrase_type": "architecture_comparison",
                    "quote": "multiple architectures: CNN, GNN, and hybrid",
                    "context": "We prototyped multiple architectures...",
                    "confidence": 0.75,
                },
                # ...
            ],
            "parameter_optimizations": [...],
            "alternative_approaches": [...],
            "testing_approaches": [...],
            "failure_learnings": [...],
            "hypotheses_tested": [...],
            "evidence_strength": "strong",  # weak|moderate|strong
            "audit_ready_summary": "...",
        },
    },
}
```

---

## Performance

All features are **fast** (no LLM calls):
- **Decomposition**: ~5-10ms
- **Uncertainty Detection**: ~20-50ms
- **Evidence Extraction**: ~20-50ms
- **Total**: ~100-200ms for typical projects

Safe to run on every project without performance concerns.

---

## Configuration

### Add Custom Keywords (for Decomposition)
Edit keywords in `app/advanced_nlp.py`:

```python
RESEARCH_KEYWORDS = {
    "algorithm", "ml", "ai", "prototype",  # existing
    "your_keyword", "your_keyword2",        # add custom
}

INFRASTRUCTURE_KEYWORDS = {
    # ... add custom infrastructure keywords
}
```

### Add Custom Patterns (for Uncertainty/Evidence)
Edit patterns in `app/advanced_nlp.py`:

```python
UNCERTAINTY_PATTERNS = {
    "technical_unknown": [
        r"uncertain.*how|how.*uncertain",   # existing
        r"your_custom_pattern",             # add custom
    ]
}
```

---

## Backward Compatibility

✅ **Zero Breaking Changes**
- Existing `analyze_project()` unchanged
- Existing `analyze_project_async()` unchanged
- New features are **optional** - default behavior unchanged
- All Phase 1-3 features work exactly as before

---

## Demo

Run demonstration on sample projects:

```bash
python demo_advanced_nlp.py
```

This shows:
1. Navigation System (mixed project: 82% eligible)
2. Compression Algorithm (research project: 78% eligible)
3. Marketing Platform (business project: no technical elements)

For each project, demonstrates all three features.

---

## Troubleshooting

### Issue: No results in decomposition
**Cause**: Description too short or uses different vocabulary  
**Solution**: Add keywords to `RESEARCH_KEYWORDS`, etc. in `advanced_nlp.py`

### Issue: Uncertainty score 0.0
**Cause**: Project description doesn't mention experiments/uncertainty  
**Solution**: Check if project really lacks experimentation evidence

### Issue: Evidence strength "weak"
**Cause**: Phrases are too vague or use different wording  
**Solution**: Add patterns to `EXPERIMENTATION_PATTERNS` in `advanced_nlp.py`

### Issue: Module not found
**Cause**: advanced_nlp.py not installed/imported  
**Solution**: Ensure `app/advanced_nlp.py` exists and use correct import: `from app.advanced_nlp import ...`

---

## FAQ

**Q: Do Phase 4 features require the LLM/API?**  
A: No. All features are regex/keyword-based and work without any API calls.

**Q: Can I run Phase 4 on all projects?**  
A: Yes, and it's recommended. Features are fast (<200ms) and provide audit value.

**Q: How do I disable Phase 4?**  
A: Use `analyze_project()` instead of `analyze_project_with_advanced_nlp()`.

**Q: Can I use Phase 4 features alone?**  
A: Yes. Import `ProjectDecomposer`, `UncertaintyDetector`, `ExperimentationExtractor` directly.

**Q: Are Phase 4 results used in Form 6765 generation?**  
A: Not automatically, but you can integrate: use decomposition to calculate eligible % and multiply wages accordingly.

**Q: Can I customize the keywords/patterns?**  
A: Yes. Edit `RESEARCH_KEYWORDS`, `UNCERTAINTY_PATTERNS`, etc. in `app/advanced_nlp.py`.

---

## Next Steps

1. **Try it**: Run `demo_advanced_nlp.py` to see examples
2. **Integrate**: Use `analyze_project_with_advanced_nlp()` in your workflow
3. **Customize**: Add keywords/patterns for your specific projects
4. **Monitor**: Track decomposition, uncertainty, and evidence metrics
5. **Enhance**: Consider LLM-based decomposition later for higher accuracy

---

## Support

For issues or questions:
1. Check `PHASE_4_ADVANCED_NLP.md` for detailed documentation
2. Review `demo_advanced_nlp.py` for working examples
3. Check code comments in `app/advanced_nlp.py`
4. Examine test output in demo script
