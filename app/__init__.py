"""
R&D Tax Credit Analysis Platform
Phase 1-2 Implementation: Intelligent Hybrid Decision Engine + Prime R&D Filing Features
"""

from .reasoning import (
    analyze_project,
    analyze_project_async,
    analyze_project_strict,
    analyze_with_dual_check,
    analyze_project_with_advanced_nlp,
    rule_out_classifier,
    rule_based_classifier,
)

from .qre_categorization import (
    ExpenseItem,
    QRECategoryization,
    categorize_expenses,
    calculate_eligible_wages,
    get_rd_percentage_for_role,
)

from .form_6765_generator import (
    Form6765Data,
    Form6765Generator,
    GrossReceiptsPeriod,
)

from .audit_defense_pack import (
    AuditDefensePack,
    AuditDefenseGenerator,
    TechnologicalUncertainty,
    ExperimentationEvidence,
    TeamContribution,
    CodeArtifact,
)

from .audit_trail_enhanced import (
    AuditTrailManager,
    TracePacket,
    TraceSignature,
)

from .advanced_nlp import (
    ProjectDecomposer,
    ProjectComponent,
    ProjectDecomposition,
    UncertaintyDetector,
    UncertaintyAnalysis,
    ExperimentationExtractor,
    ExperimentationEvidence,
    ComponentType,
)

__all__ = [
    # Phase 1: Hybrid Decision Engine
    "analyze_project",
    "analyze_project_async",
    "analyze_project_strict",
    "analyze_with_dual_check",
    "analyze_project_with_advanced_nlp",
    "rule_out_classifier",
    "rule_based_classifier",
    # Phase 2.1: QRE Categorization
    "ExpenseItem",
    "QRECategoryization",
    "categorize_expenses",
    "calculate_eligible_wages",
    "get_rd_percentage_for_role",
    # Phase 2.2: Form 6765 Generator
    "Form6765Data",
    "Form6765Generator",
    "GrossReceiptsPeriod",
    # Phase 2.3: Audit Defense Pack
    "AuditDefensePack",
    "AuditDefenseGenerator",
    "TechnologicalUncertainty",
    "ExperimentationEvidence",
    "TeamContribution",
    "CodeArtifact",
    # Phase 2.4: Enhanced Audit Trail
    "AuditTrailManager",
    "TracePacket",
    "TraceSignature",
    # Phase 4: Advanced NLP Features
    "ProjectDecomposer",
    "ProjectComponent",
    "ProjectDecomposition",
    "ComponentType",
    "UncertaintyDetector",
    "UncertaintyAnalysis",
    "ExperimentationExtractor",
    "ExperimentationEvidence",
]
