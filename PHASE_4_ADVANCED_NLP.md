# Phase 4: Advanced NLP Features Documentation

## Overview

Phase 4 introduces three advanced NLP-based features to enhance R&D tax credit classification accuracy:

1. **Project Decomposition (4.1)** - Break complex projects into research vs non-research components
2. **Uncertainty Detector (4.2)** - Identify technical unknowns, experiments, benchmarks, and failures
3. **Experimentation Evidence Extractor (4.3)** - Extract specific phrases showing systematic experimentation

These features work **alongside** the existing Phases 1-3 (tiered decision engine, QRE categorization, form generation, audit trails) and are **fully backward compatible**.

---

## Feature Details

### 4.1 Project Decomposition

**Purpose**: Break complex projects into discrete components and evaluate each separately.

**Problem Solved**: Many projects are genuinely mixed - some components are R&D-eligible, others aren't. Simple yes/no classification misses this nuance.

**How It Works**:
- Analyzes project description using keyword-based classification
- Identifies components in five categories:
  - **RESEARCH** - Eligible for credit (algorithms, ML, optimization, prototyping)
  - **INFRASTRUCTURE** - Not eligible (DevOps, deployment, hosting, CI/CD)
  - **MAINTENANCE** - Not eligible (bug fixes, technical debt, routine updates)
  - **SUPPORT** - Not eligible (documentation, training, knowledge base)
  - **BUSINESS** - Not eligible (marketing, sales, HR, finance)

**Example Output**:
```
Project: Navigation System Overhaul

Components:
  1. ML Pathfinding Algorithm
     - Type: RESEARCH
     - Eligible: true
     - Estimated %: 60%
  
  2. Dashboard UI Redesign  
     - Type: INFRASTRUCTURE
     - Eligible: false
     - Estimated %: 25%
  
  3. Legacy Data Migration
     - Type: MAINTENANCE
     - Eligible: false
     - Estimated %: 15%

Overall Eligibility: PARTIALLY_ELIGIBLE (60% of effort is research)
```

**Classes**:
```python
class ProjectComponent:
    name: str
    description: str
    component_type: ComponentType  # enum
    estimated_percentage: float
    rationale: str
    eligible: bool
    confidence: float

class ProjectDecomposition:
    project_id: str
    total_components: int
    components: List[ProjectComponent]
    research_percentage: float
    eligible_percentage: float
    overall_eligibility: str  # "eligible", "partially_eligible", "not_eligible"
```

**Usage**:
```python
from app.advanced_nlp import ProjectDecomposer

decomposer = ProjectDecomposer()
result = decomposer.decompose_project(
    project_id="PROJ-001",
    project_name="My Project",
    project_description="Project description...",
    use_llm=False,  # Can be enhanced with LLM later
)

print(f"Eligible percentage: {result.eligible_percentage * 100:.1f}%")
for component in result.components:
    print(f"  - {component.name}: {component.eligible}")
```

---

### 4.2 Uncertainty Detector

**Purpose**: Identify evidence of technical uncertainty, which is a key IRS §41 requirement.

**Problem Solved**: The "elimination of uncertainty" criterion is hard to measure. This detector finds concrete signals.

**What It Detects**:
- **Technical Unknowns** - Phrases like "uncertain how", "unclear method", "feasibility question"
- **Experiments** - Phrases like "tested", "experimented", "tried multiple", "evaluated options"
- **Benchmarks** - Phrases like "benchmark", "performance metric", "latency", "accuracy test"
- **Failures** - Phrases like "failed", "didn't work", "unexpected result", "learned from"
- **New Methods** - Phrases like "novel", "new approach", "invented", "unique", "first time"

**Example Output**:
```
Project: Novel Compression Algorithm

Uncertainty Analysis:
  Has Technical Unknowns: true
  Has Experiments: true
  Has Benchmarks: true
  Has Failures: true
  Has New Methods: true
  Overall Uncertainty Score: 0.85

Detected Indicators:
  - technical_unknown: "Initial approaches using standard Huffman coding couldn't achieve 50% ratio"
  - experiment: "experimented with three different frame-difference techniques"
  - benchmark: "Benchmarking against industry standards revealed optical flow achieved 45%"
  - failure: "failures with motion estimation on fast scenes"
  - new_method: "developed a novel lossless compression algorithm"

Missing Evidence:
  - None (all indicators present)

Rationale: Project shows strong evidence of technical uncertainty, systematic 
experimentation, performance benchmarking, and documented failures - all key 
indicators of R&D eligibility under IRS §41.
```

**Classes**:
```python
class UncertaintyIndicator:
    indicator_type: str  # "technical_unknown", "experiment", "benchmark", etc.
    description: str
    confidence: float
    evidence_phrases: List[str]

class UncertaintyAnalysis:
    has_technical_unknowns: bool
    has_experiments: bool
    has_benchmarks: bool
    has_failures: bool
    has_new_methods: bool
    overall_uncertainty_score: float  # 0.0-1.0
    indicators: List[UncertaintyIndicator]
    missing_evidence: List[str]
```

**Usage**:
```python
from app.advanced_nlp import UncertaintyDetector

detector = UncertaintyDetector()
result = detector.detect_uncertainties("Project description...")

if result.overall_uncertainty_score > 0.7:
    print("Strong evidence of technical uncertainty")

for indicator in result.indicators:
    print(f"  {indicator.indicator_type}: {indicator.description}")
```

---

### 4.3 Experimentation Evidence Extractor

**Purpose**: Extract specific phrases that demonstrate systematic experimentation for audit defense.

**Problem Solved**: When audited, companies need concrete evidence. This extractor finds and categorizes evidence phrases.

**Evidence Categories**:
- **Architecture Comparisons** - "Compared architectures", "multiple approaches", "design alternatives"
- **Parameter Optimization** - "Optimized parameters", "tuned hyperparameters", "grid search"
- **Alternative Approaches** - "Tried approaches", "alternative methods", "different strategies"
- **Testing Approaches** - "Tested strategies", "A/B testing", "performance benchmarks"
- **Failure Learnings** - "Initial failures", "learned from failures", "unexpected results"
- **Hypothesis Testing** - "Hypothesis testing", "proof of concept", "validate approach"

**Example Output**:
```
Project: ML Pathfinding Algorithm

Experimentation Evidence Summary: STRONG
  - 3 architecture comparisons
  - 2 parameter optimizations
  - 1 alternative approach
  - 4 testing approaches
  - 2 failure learnings
  - 3 hypotheses tested
  Total Phrases: 15

Audit-Ready Summary:
  "Experimentation Evidence (strong): 3 architecture comparisons, 
   2 parameter optimizations, 1 alternative approach, 4 testing approaches, 
   2 failure learnings, 3 hypotheses tested"

Extracted Phrases:
  
  Architecture Comparisons:
    1. "prototyped multiple architectures: CNN, GNN, and hybrid approaches"
       Context: "We prototyped multiple architectures: CNN, GNN, and hybrid..."
  
  Parameter Optimizations:
    1. "optimized parameters through grid search"
       Context: "We optimized parameters through grid search and discovered..."
  
  Failure Learnings:
    1. "first attempt with a basic GNN failed due to memory constraints"
       Context: "Our first attempt with a basic GNN failed due to memory..."
```

**Classes**:
```python
class ExperimentationPhrase:
    phrase_type: str
    quote: str  # Exact text from description
    context: str  # Surrounding sentences
    confidence: float

class ExperimentationEvidence:
    project_id: str
    total_phrases_found: int
    architecture_comparisons: List[ExperimentationPhrase]
    parameter_optimizations: List[ExperimentationPhrase]
    alternative_approaches: List[ExperimentationPhrase]
    testing_approaches: List[ExperimentationPhrase]
    failure_learnings: List[ExperimentationPhrase]
    hypotheses_tested: List[ExperimentationPhrase]
    evidence_strength: str  # "weak", "moderate", "strong"
    audit_ready_summary: str
```

**Usage**:
```python
from app.advanced_nlp import ExperimentationExtractor

extractor = ExperimentationExtractor()
result = extractor.extract_evidence(
    project_id="PROJ-001",
    project_description="Project description..."
)

print(f"Evidence Strength: {result.evidence_strength}")
print(f"Total Phrases: {result.total_phrases_found}")

# Use in audit defense generation
for phrase in result.architecture_comparisons:
    print(f"  Quote: {phrase.quote}")
    print(f"  Context: {phrase.context}")
```

---

## Integration with Main Pipeline

### Option 1: Simple Integration (Backward Compatible)

Use the new `analyze_project_with_advanced_nlp()` function:

```python
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp

record = ProjectRecord(
    project_id="PROJ-001",
    project_name="My Project",
    description="Project description...",
)

result = analyze_project_with_advanced_nlp(
    record=record,
    enable_decomposition=True,
    enable_uncertainty=True,
    enable_evidence=True,
)

# Result contains:
# - result["classification"]  - Basic eligibility (from Phase 1-3)
# - result["trace"]           - Audit trail
# - result["advanced_nlp"]["decomposition"]  - Component breakdown
# - result["advanced_nlp"]["uncertainty"]    - Uncertainty score
# - result["advanced_nlp"]["evidence"]       - Evidence phrases
```

### Option 2: Selective Enablement

Run only specific features:

```python
result = analyze_project_with_advanced_nlp(
    record=record,
    enable_decomposition=True,   # Only run decomposition
    enable_uncertainty=False,
    enable_evidence=False,
)
```

### Option 3: Individual Feature Usage

Use features independently:

```python
from app.advanced_nlp import ProjectDecomposer, UncertaintyDetector, ExperimentationExtractor

# Decomposition only
decomposer = ProjectDecomposer()
decomp = decomposer.decompose_project(project_id, name, description)

# Uncertainty only
detector = UncertaintyDetector()
uncertainty = detector.detect_uncertainties(description)

# Evidence only
extractor = ExperimentationExtractor()
evidence = extractor.extract_evidence(project_id, description)
```

---

## Example Workflow

```python
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp
from app.qre_categorization import categorize_expenses
from app.audit_defense_pack import AuditDefenseGenerator

# 1. Analyze project eligibility (with advanced NLP)
project = ProjectRecord(
    project_id="PROJ-NAV-001",
    project_name="Navigation System",
    description="We built a navigation system with ML pathfinding...",
)

analysis = analyze_project_with_advanced_nlp(project)

# Check eligibility
if analysis["classification"]["eligible"]:
    # 2. Decompose to understand which components are eligible
    decomp = analysis["advanced_nlp"]["decomposition"]
    print(f"Eligible: {decomp['eligible_percentage']*100:.0f}%")
    
    # 3. Get uncertainty score for Four-Part Test
    uncertainty = analysis["advanced_nlp"]["uncertainty"]
    print(f"Uncertainty evidence: {uncertainty['overall_uncertainty_score']:.2f}")
    
    # 4. Extract evidence for audit defense
    evidence = analysis["advanced_nlp"]["evidence"]
    print(f"Evidence strength: {evidence['evidence_strength']}")
    
    # 5. Generate audit defense using extracted evidence
    audit_gen = AuditDefenseGenerator()
    defense = audit_gen.generate(
        project_id=project.project_id,
        description=analysis["advanced_nlp"],  # Pass advanced results
        team_members=["Alice", "Bob"],
        expenses=[],
    )
    
    # 6. Export defense pack
    defense.to_json("audit_defense.json")
    defense.to_markdown("audit_defense.md")
```

---

## Configuration & Tuning

### Keyword Lists

All keyword-based detection uses customizable keyword lists at the top of `advanced_nlp.py`:

```python
RESEARCH_KEYWORDS = {
    "algorithm", "ml", "ai", "prototype", "experimentation", "novel",
    # ... more keywords
}

INFRASTRUCTURE_KEYWORDS = {
    "deployment", "devops", "ci/cd", "docker", "kubernetes",
    # ... more keywords
}
```

To add custom keywords, modify these sets.

### Pattern Customization

All pattern-based detection uses regex patterns in `UNCERTAINTY_PATTERNS` and `EXPERIMENTATION_PATTERNS`:

```python
UNCERTAINTY_PATTERNS = {
    "technical_unknown": [
        r"uncertain.*how|how.*uncertain",
        r"whether.*could|could.*whether",
        # ... more patterns
    ]
}
```

To improve detection, add more regex patterns.

### Confidence Tuning

Confidence scores can be adjusted in each detector class.

---

## Performance Considerations

- **Decomposition**: O(n) on description length (linear keyword scan)
- **Uncertainty Detection**: O(n*m) where n=description length, m=num patterns (~50ms for 5KB)
- **Evidence Extraction**: O(n*m) similar to uncertainty detection (~50ms for 5KB)
- **Full Analysis**: ~100-200ms for typical project descriptions (no LLM calls)

All three features are **extremely fast** and can be run on every project without performance impact.

---

## Testing

Run the demonstration:

```bash
python demo_advanced_nlp.py
```

This tests all three features on sample projects including:
- Complex mixed projects (navigation system)
- Pure research projects (compression algorithm)
- Business-only projects (marketing platform)

---

## Future Enhancements

1. **LLM-based Decomposition**: Add optional LLM-powered decomposition for higher accuracy
2. **Custom Keyword Management**: UI to manage and test custom keywords
3. **ML-based Classification**: Train small classifier for component types
4. **Evidence Weighting**: Weight phrases by relevance to specific IRS §41 criteria
5. **Cross-validation**: Compare keyword-based vs LLM-based evidence extraction
6. **Integration with Form 6765**: Auto-calculate eligible wages by component type

---

## Summary

**Phase 4** delivers three powerful NLP features that:

✅ **Improve Accuracy** - Decomposition catches mixed projects  
✅ **Audit-Ready** - Evidence extraction provides concrete documentation  
✅ **IRS Aligned** - Detects technical uncertainty directly from §41 requirements  
✅ **Fast** - Sub-second analysis on any project description  
✅ **Flexible** - Optional, can be used independently or together  
✅ **Backward Compatible** - Zero impact on existing code  

These features are **optional add-ons** that enhance the core decision engine without modifying it.
