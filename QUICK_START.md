# Quick Start Guide: Phase 1-2 Implementation

## Installation

All modules are in `app/`:
- `app/reasoning.py` — Tiered decision engine (Phases 1.1-1.3)
- `app/qre_categorization.py` — QRE expense classification (Phase 2.1)
- `app/form_6765_generator.py` — Form 6765 auto-generation (Phase 2.2)
- `app/audit_defense_pack.py` — Audit defense documentation (Phase 2.3)
- `app/audit_trail_enhanced.py` — Immutable audit trail (Phase 2.4)

## Usage Examples

### Phase 1: Analyze a Project (Tiered Decision Engine)

```python
from app import analyze_project
from app.models import ProjectRecord

# Create a project
project = ProjectRecord(
    project_id="P-1001",
    project_name="ML Pipeline Optimization",
    description="Developed new feature extraction algorithm to reduce training time 40%"
)

# Analyze (automatic tiering: Rule-Out → Rule-Based → LLM)
classification, trace = analyze_project(project, user_id="alice@company.com")

print(f"Eligible: {classification.eligible}")
print(f"Confidence: {classification.confidence:.2%}")
print(f"Rationale: {classification.rationale}")

# Trace shows which tier was used
for step in trace["steps"]:
    print(f"  {step['action']}: {step['model_name']}")
```

### Phase 1: Optional Dual-Model Cross-Check

```python
from app import analyze_with_dual_check

# Run primary + verifier models
result, trace, verification = analyze_with_dual_check(
    project,
    primary_model="gpt-4o-mini",
    verifier_model="gpt-3.5-turbo"
)

if verification["needs_manual_review"]:
    print(f"⚠️ Manual review needed: {verification['mismatch_count']} criteria mismatches")
else:
    print(f"✅ Dual-check passed: {result.eligible}")
```

### Phase 2.1: Categorize Expenses (QRE)

```python
from app import categorize_expenses, ExpenseItem

# Create expense items
expenses = [
    ExpenseItem(
        id="1",
        description="AWS EC2 instances for ML training",
        amount=15000,
    ),
    ExpenseItem(
        id="2",
        description="Senior ML engineer salary Q4",
        amount=50000,
        employee_id="emp-123",
        employee_role="ml engineer",
        hours=500,  # Hours spent on R&D
    ),
    ExpenseItem(
        id="3",
        description="Software license for JetBrains IDE",
        amount=2000,
    ),
]

# Categorize
qre = categorize_expenses(
    expenses,
    project_id="P-1001",
    conservative=True  # Use lower-bound %s for wages
)

print(f"Total QRE: ${qre.total_qre:,.2f}")
print(f"  Wages: ${qre.wages:,.2f}")
print(f"  Cloud: ${qre.cloud_computing:,.2f}")
print(f"  Supplies: ${qre.supplies:,.2f}")
print(f"  Contract R: ${qre.contract_research:,.2f}")
```

### Phase 2.2: Generate Form 6765

```python
from app import Form6765Generator, GrossReceiptsPeriod

gen = Form6765Generator()

# Generate form with QRE data
form_data = gen.generate(
    project_id="P-1001",
    tax_year=2024,
    qre_data={
        "wages": 150000,
        "supplies": 5000,
        "cloud_computing": 25000,
        "contract_research_65pct": 10000,
    },
    gross_receipts_history=[
        GrossReceiptsPeriod(2023, 50_000_000),
        GrossReceiptsPeriod(2022, 48_000_000),
    ],
    use_asc=False,  # Use regular credit (not ASC)
    num_employees=45,
    filing_status="Corporation",
)

print(f"Total QRE: ${form_data.total_qre:,.2f}")
print(f"Regular Credit: ${form_data.regular_credit:,.2f}")
print(f"Total Credit: ${form_data.total_credit:,.2f}")

# Export in multiple formats
json_form = gen.to_json()              # For DB storage
csv_form = gen.to_csv()                 # For Excel
gen.to_pdf("form_6765_2024.pdf")       # For review/filing
```

### Phase 2.3: Generate Audit Defense Pack

```python
from app import (
    AuditDefenseGenerator,
    TechnologicalUncertainty,
    ExperimentationEvidence,
    TeamContribution,
    CodeArtifact,
)

gen = AuditDefenseGenerator()

pack = gen.generate(
    project_id="P-1001",
    project_name="ML Pipeline Optimization",
    project_description="Developed feature extraction to reduce training time",
    eligibility_determination={
        "permitted_purpose": "met",
        "elimination_uncertainty": "met",
        "process_experimentation": "met",
        "technological_nature": "met",
    },
    technological_uncertainty=TechnologicalUncertainty(
        problem_statement="Could we achieve 40% training time reduction?",
        uncertainty_type="performance",
        alternative_approaches=[
            "Baseline: existing feature extraction",
            "Approach A: PCA-based dimensionality reduction",
            "Approach B: Custom neural architecture",
        ],
        evidence_of_uncertainty=[
            "Design docs show 3 competing approaches tested",
            "Performance metrics varied 15-45% across iterations",
        ]
    ),
    experimentation_evidence=[
        ExperimentationEvidence(
            hypothesis="Custom NN can match baseline with 50% fewer features",
            methodology="Ablation study on architecture depth/width",
            test_approach="Train 12 variants on 100M sample dataset",
            results_summary="Achieved 40% speedup with <1% accuracy loss",
            failure_or_learning="Initial approach failed on edge cases; added dropout & regularization",
            iteration_count=5,
            key_metrics={
                "training_time": "12h → 7.2h",
                "accuracy": "92.5% → 91.8%",
                "inference_latency": "45ms → 28ms",
            }
        )
    ],
    code_artifacts=[
        CodeArtifact(
            repository="company/ml-pipeline",
            commit_hash="abc123def456789",
            commit_date="2024-06-15T10:30:00Z",
            commit_message="Implement custom feature extraction layer",
            author="bob@company.com",
            file_path="src/extractors/custom_nn.py",
            lines_changed=350,
            description="Core neural network implementation for optimized feature extraction",
        )
    ],
    team_contributions=[
        TeamContribution(
            name="Bob Smith",
            role="ML Engineer",
            estimated_hours=400,
            contribution_area="Architecture design, experimentation",
            start_date="2024-04-01",
            end_date="2024-06-30",
            key_decisions=[
                "Chose custom NN over transfer learning",
                "Selected Adam optimizer with learning rate decay",
                "Implemented early stopping based on val loss",
            ],
        ),
        TeamContribution(
            name="Carol Johnson",
            role="Data Scientist",
            estimated_hours=200,
            contribution_area="Data preparation, evaluation metrics",
            start_date="2024-04-15",
            end_date="2024-06-30",
            key_decisions=["Designed ablation study", "Set acceptance criteria"],
        ),
    ],
)

# Export for review
json_pack = gen.to_json()  # For storage
markdown_pack = gen.to_markdown()  # For human review
print(markdown_pack)
```

### Phase 2.4: Immutable Audit Trail

```python
from app import AuditTrailManager

# Initialize (optional S3 for archival)
manager = AuditTrailManager(
    ledger_path=".audit_trail",
    signing_key="your-secret-key",  # Or set env var
    s3_bucket=None,  # Optional: "my-audit-bucket"
)

# Create & sign a decision
packet = manager.create_packet(
    project_id="P-1001",
    decision="eligible",
    confidence=0.92,
    rationale="Meets all 4 criteria: permitted purpose, uncertainty, experimentation, technological.",
    data={
        "permitted_purpose": "met",
        "elimination_uncertainty": "met",
        "process_experimentation": "met",
        "technological_nature": "met",
        "tier_used": "LLM (Tier 3)",
    }
)

# Append to immutable ledger
manager.append_packet(packet)

# Later: retrieve & verify
trail = manager.get_project_trail("P-1001")
for p in trail:
    is_valid = manager.verify_packet(p)
    print(f"{p.packet_id}: {p.decision} (valid={is_valid})")

# Generate audit report
audit_json = manager.export_audit_report("P-1001", format="json")
audit_md = manager.export_audit_report("P-1001", format="markdown")
```

## Environment Configuration

### Optional Settings

```bash
# LLM Model Selection
export OPENAI_MODEL="gpt-4o-mini"              # Primary model
export OPENAI_MODEL_FALLBACK="gpt-3.5-turbo"   # Fallback if primary unavailable

# Audit Trail Signing
export AUDIT_TRAIL_SIGNING_KEY="your-secret-256bit-key"

# S3 Archival (optional)
export AUDIT_TRAIL_S3_BUCKET="my-audit-bucket"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
```

## Common Workflows

### Workflow 1: Simple Eligibility Check

```python
from app import analyze_project
from app.models import ProjectRecord

project = ProjectRecord(project_id="P-1", description="...")
cls, _ = analyze_project(project)
print(f"Eligible: {cls.eligible}")
```

### Workflow 2: Full Filing Package

```python
from app import (
    analyze_project,
    categorize_expenses,
    Form6765Generator,
    AuditDefenseGenerator,
    AuditTrailManager,
)

# 1. Determine eligibility
project = ProjectRecord(...)
cls, trace = analyze_project(project)

if not cls.eligible:
    print("Not eligible, skipping filing")
else:
    # 2. Categorize expenses
    expenses = [...]
    qre = categorize_expenses(expenses, project.project_id)
    
    # 3. Generate Form 6765
    gen = Form6765Generator()
    form = gen.generate(
        project_id=project.project_id,
        tax_year=2024,
        qre_data={
            "wages": qre.wages,
            "supplies": qre.supplies,
            "cloud_computing": qre.cloud_computing,
            "contract_research_65pct": qre.contract_research * 0.65,
        },
    )
    print(f"Credit: ${form.total_credit:,.2f}")
    gen.to_pdf(f"{project.project_id}_form_6765.pdf")
    
    # 4. Generate audit defense pack
    audit_gen = AuditDefenseGenerator()
    pack = audit_gen.generate(
        project_id=project.project_id,
        project_name=project.project_name,
        project_description=project.description,
        eligibility_determination={...},
        # ... other params
    )
    print(audit_gen.to_markdown())
    
    # 5. Record in audit trail
    manager = AuditTrailManager()
    packet = manager.create_packet(
        project_id=project.project_id,
        decision="eligible",
        confidence=cls.confidence,
        rationale=cls.rationale,
        data={...}
    )
    manager.append_packet(packet)

print("✅ Filing package complete!")
```

### Workflow 3: Audit Verification

```python
from app import AuditTrailManager

manager = AuditTrailManager()

# Get audit trail for project
trail = manager.get_project_trail("P-1001")

# Verify all packets
all_valid = all(manager.verify_packet(p) for p in trail)
print(f"Audit trail valid: {all_valid}")

# Export for IRS submission
report = manager.export_audit_report("P-1001", format="json")
with open("audit_report.json", "w") as f:
    f.write(report)
```

## Troubleshooting

**Q: "Invalid model ID" error**
A: The LLM fallback chain automatically tries alternatives. Check `OPENAI_MODEL` env var.

**Q: PDF export fails**
A: Install reportlab: `pip install reportlab`

**Q: Audit trail not being signed**
A: Set `AUDIT_TRAIL_SIGNING_KEY` env var or pass it to `AuditTrailManager()`.

**Q: QRE calculations seem high**
A: Review role percentages in `ROLE_RD_PERCENTAGES`. Use `conservative=True` for lower estimates.

## Next Steps

1. **Integrate with DB:** Store `Form6765Data` and `AuditDefensePack` for querying
2. **Web Dashboard:** Build UI to visualize QRE breakdown & audit trail
3. **Batch Processing:** Process multiple projects in parallel
4. **Git Integration:** Auto-fetch commits for `CodeArtifact` population
5. **Historical Analysis:** Track QRE trends year-over-year

---

**Questions?** Check `IMPLEMENTATION_SUMMARY.md` for detailed architecture.
