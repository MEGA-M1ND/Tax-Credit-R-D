#!/usr/bin/env python3
"""
Demonstration of Phase 4 Advanced NLP Features:
- 4.1 Project Decomposition
- 4.2 Uncertainty Detector  
- 4.3 Experimentation Evidence Extractor
"""

import json
import sys
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp
from app.advanced_nlp import (
    ProjectDecomposer,
    UncertaintyDetector,
    ExperimentationExtractor,
)


# Example project descriptions for testing
SAMPLE_PROJECTS = {
    "complex_navigation": {
        "project_id": "PROJ-NAV-001",
        "project_name": "Navigation System Overhaul",
        "description": """
We undertook a comprehensive overhaul of our navigation system to address significant performance limitations.
The project had three major components:

1. ML Pathfinding Algorithm (Research)
We were uncertain whether a neural network could improve pathfinding efficiency compared to A*.
We prototyped multiple architectures: CNN, GNN, and hybrid approaches. Through systematic experimentation,
we tested each on 100,000 road networks, measuring latency and accuracy. Our first attempt with a basic GNN
failed due to memory constraints. We then optimized parameters through grid search and discovered a 40% 
improvement with fewer layers. We evaluated alternative activation functions and found ReLU + BatchNorm best.
This process of trying multiple formulations and comparing performance metrics was critical to our success.

2. Dashboard UI Redesign (Not Research)
We redesigned the user dashboard interface to improve aesthetics and usability. This involved standard UI/UX
work like button placement, color schemes, and responsive design. No technical uncertainty was involved.

3. Legacy Data Migration (Not Research)
We migrated data from our old system to the new one. This was routine data transformation work with no
novel technical approaches or uncertainty involved.
        """
    },
    "algorithm_research": {
        "project_id": "PROJ-ALG-002",
        "project_name": "Novel Compression Algorithm",
        "description": """
We developed a novel lossless compression algorithm targeting streaming video data. Initial approaches using
standard Huffman coding couldn't achieve the required 50% compression ratio. We hypothesized that exploiting 
temporal redundancy would help. We experimented with three different frame-difference techniques: pixel-level
delta, DCT coefficients, and optical flow vectors. Benchmarking against industry standards revealed that our
optical flow approach achieved 45% compression, close to target. We tested various parameter settings and 
discovered motion smoothing improved results by additional 8%. Our team documented failures with motion 
estimation on fast scenes and the learnings that informed our smoothing fix. The entire process was driven
by systematic hypothesis testing and comparative evaluation against baselines.
        """
    },
    "business_project": {
        "project_id": "PROJ-BIZ-003",
        "project_name": "Marketing Automation Platform",
        "description": """
We built a marketing automation platform to streamline customer outreach. The platform includes email
templating, scheduling, and analytics. We updated our website styling and marketing materials. Our team
conducted market research to understand competitor offerings and customer preferences. We hired additional
sales staff to support growth.
        """
    },
}


def demo_decomposition(project_name: str, description: str) -> None:
    """Demonstrate Project Decomposition (4.1)."""
    print(f"\n{'='*80}")
    print(f"4.1 PROJECT DECOMPOSITION: {project_name}")
    print(f"{'='*80}")
    
    decomposer = ProjectDecomposer()
    result = decomposer.decompose_project(
        project_id=f"{project_name.replace(' ', '_')}",
        project_name=project_name,
        project_description=description,
        use_llm=False,
    )
    
    print(f"\nTotal Components: {result.total_components}")
    print(f"Research Percentage: {result.research_percentage*100:.1f}%")
    print(f"Eligible Percentage: {result.eligible_percentage*100:.1f}%")
    print(f"Overall Eligibility: {result.overall_eligibility}")
    print(f"\nComponents:")
    for i, component in enumerate(result.components, 1):
        print(f"\n  [{i}] {component.name}")
        print(f"      Type: {component.component_type.value}")
        print(f"      Eligible: {component.eligible}")
        print(f"      Est. Percentage: {component.estimated_percentage:.1f}%")
        print(f"      Rationale: {component.rationale}")
        print(f"      Confidence: {component.confidence:.2f}")


def demo_uncertainty(project_name: str, description: str) -> None:
    """Demonstrate Uncertainty Detection (4.2)."""
    print(f"\n{'='*80}")
    print(f"4.2 UNCERTAINTY DETECTOR: {project_name}")
    print(f"{'='*80}")
    
    detector = UncertaintyDetector()
    result = detector.detect_uncertainties(description)
    
    print(f"\nTechnical Unknowns: {result.has_technical_unknowns}")
    print(f"Experiments Performed: {result.has_experiments}")
    print(f"Benchmarks Attempted: {result.has_benchmarks}")
    print(f"Failures Documented: {result.has_failures}")
    print(f"New Methods Researched: {result.has_new_methods}")
    print(f"Overall Uncertainty Score: {result.overall_uncertainty_score:.2f}")
    print(f"\nDetected Indicators: {len(result.indicators)}")
    for i, indicator in enumerate(result.indicators[:5], 1):  # Show first 5
        print(f"  [{i}] {indicator.indicator_type}: {indicator.description}")
    
    if result.missing_evidence:
        print(f"\nMissing Evidence:")
        for item in result.missing_evidence[:3]:
            print(f"  - {item}")
    
    print(f"\nRationale: {result.rationale}")


def demo_evidence(project_name: str, description: str) -> None:
    """Demonstrate Experimentation Evidence Extraction (4.3)."""
    print(f"\n{'='*80}")
    print(f"4.3 EXPERIMENTATION EVIDENCE EXTRACTOR: {project_name}")
    print(f"{'='*80}")
    
    extractor = ExperimentationExtractor()
    result = extractor.extract_evidence(
        project_id=f"{project_name.replace(' ', '_')}",
        project_description=description,
    )
    
    print(f"\nTotal Phrases Found: {result.total_phrases_found}")
    print(f"Evidence Strength: {result.evidence_strength.upper()}")
    print(f"\nAudit-Ready Summary:")
    print(f"  {result.audit_ready_summary}")
    
    print(f"\nEvidence by Category:")
    print(f"  Architecture Comparisons: {len(result.architecture_comparisons)}")
    if result.architecture_comparisons:
        for phrase in result.architecture_comparisons[:2]:
            print(f"    - '{phrase.quote}'")
    
    print(f"  Parameter Optimizations: {len(result.parameter_optimizations)}")
    if result.parameter_optimizations:
        for phrase in result.parameter_optimizations[:2]:
            print(f"    - '{phrase.quote}'")
    
    print(f"  Alternative Approaches: {len(result.alternative_approaches)}")
    if result.alternative_approaches:
        for phrase in result.alternative_approaches[:2]:
            print(f"    - '{phrase.quote}'")
    
    print(f"  Testing Approaches: {len(result.testing_approaches)}")
    if result.testing_approaches:
        for phrase in result.testing_approaches[:2]:
            print(f"    - '{phrase.quote}'")
    
    print(f"  Failure Learnings: {len(result.failure_learnings)}")
    if result.failure_learnings:
        for phrase in result.failure_learnings[:2]:
            print(f"    - '{phrase.quote}'")
    
    print(f"  Hypotheses Tested: {len(result.hypotheses_tested)}")
    if result.hypotheses_tested:
        for phrase in result.hypotheses_tested[:2]:
            print(f"    - '{phrase.quote}'")


def demo_full_analysis(project_name: str, proj_dict: dict) -> None:
    """Demonstrate full integrated analysis with all three features."""
    print(f"\n{'#'*80}")
    print(f"# FULL ADVANCED NLP ANALYSIS: {project_name}")
    print(f"{'#'*80}")
    
    # Create ProjectRecord
    record = ProjectRecord(
        project_id=proj_dict["project_id"],
        project_name=proj_dict["project_name"],
        description=proj_dict["description"],
    )
    
    # Run full analysis
    result = analyze_project_with_advanced_nlp(
        record=record,
        user_id="demo-user",
        enable_decomposition=True,
        enable_uncertainty=True,
        enable_evidence=True,
    )
    
    # Show classification result
    classification = result["classification"]
    print(f"\nBASIC ELIGIBILITY ASSESSMENT:")
    print(f"  Eligible: {classification['eligible']}")
    print(f"  Confidence: {classification['confidence']:.2f}")
    print(f"  Rationale: {classification['rationale']}")
    
    # Show advanced NLP results
    advanced = result["advanced_nlp"]
    
    if "decomposition" in advanced:
        decomp = advanced["decomposition"]
        print(f"\nPROJECT DECOMPOSITION:")
        print(f"  Components: {decomp['total_components']}")
        print(f"  Eligible %: {decomp['eligible_percentage']*100:.1f}%")
        print(f"  Overall: {decomp['overall_eligibility']}")
    
    if "uncertainty" in advanced:
        uncertainty = advanced["uncertainty"]
        print(f"\nUNCERTAINTY ANALYSIS:")
        print(f"  Score: {uncertainty['overall_uncertainty_score']:.2f}")
        print(f"  Technical Unknowns: {uncertainty['has_technical_unknowns']}")
        print(f"  Experiments: {uncertainty['has_experiments']}")
        print(f"  Benchmarks: {uncertainty['has_benchmarks']}")
    
    if "evidence" in advanced:
        evidence = advanced["evidence"]
        print(f"\nEXPERIMENTATION EVIDENCE:")
        print(f"  Phrases Found: {evidence['total_phrases_found']}")
        print(f"  Strength: {evidence['evidence_strength'].upper()}")


def main():
    """Run all demonstrations."""
    print("\n" + "="*80)
    print("PHASE 4: ADVANCED NLP FEATURES DEMONSTRATION")
    print("="*80)
    print("\nThis demo showcases three new NLP capabilities:")
    print("  4.1 Project Decomposition - Break projects into research/non-research")
    print("  4.2 Uncertainty Detector - Identify technical unknowns & experiments")
    print("  4.3 Evidence Extractor - Extract experimentation phrases for audit defense")
    
    # Run demos for each sample project
    for project_key, project_data in SAMPLE_PROJECTS.items():
        name = project_data["project_name"]
        desc = project_data["description"]
        
        demo_decomposition(name, desc)
        demo_uncertainty(name, desc)
        demo_evidence(name, desc)
        demo_full_analysis(name, project_data)
    
    print(f"\n{'='*80}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'='*80}\n")
    
    # Show usage example
    print("USAGE EXAMPLE:")
    print("""
from app.models import ProjectRecord
from app.reasoning import analyze_project_with_advanced_nlp

record = ProjectRecord(
    project_id="PROJ-001",
    project_name="My Project",
    description="Project description here...",
)

result = analyze_project_with_advanced_nlp(
    record=record,
    enable_decomposition=True,
    enable_uncertainty=True,
    enable_evidence=True,
)

# Access results:
print(result["classification"])  # Basic eligibility
print(result["advanced_nlp"]["decomposition"])  # Component breakdown
print(result["advanced_nlp"]["uncertainty"])    # Technical uncertainty score
print(result["advanced_nlp"]["evidence"])       # Experimentation evidence
    """)


if __name__ == "__main__":
    main()
