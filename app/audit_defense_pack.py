"""
Audit Defense Pack Generator (Phase 2.3)

For every eligible project, generates comprehensive audit defense documentation:
- Executive summary
- Description of technological uncertainty
- Evidence of experimentation
- Code artifacts / Git logs (if supplied)
- Team member contributions

This becomes the core of audit defense when IRS challenges the filing.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class CodeArtifact:
    """Reference to code artifact (commit, branch, file)."""
    repository: str
    commit_hash: str
    commit_date: str
    commit_message: str
    author: str
    file_path: str = None
    lines_changed: int = 0
    description: str = ""


@dataclass
class TeamContribution:
    """Team member R&D contribution."""
    name: str
    role: str
    estimated_hours: float
    contribution_area: str
    start_date: str
    end_date: str
    key_decisions: List[str] = field(default_factory=list)


@dataclass
class ExperimentationEvidence:
    """Evidence of systematic experimentation."""
    hypothesis: str
    methodology: str
    test_approach: str
    results_summary: str
    failure_or_learning: str
    iteration_count: int = 1
    key_metrics: Dict[str, str] = field(default_factory=dict)


@dataclass
class TechnologicalUncertainty:
    """Description of technological uncertainty."""
    problem_statement: str
    uncertainty_type: str  # "whether", "how", "which", "performance", "feasibility"
    alternative_approaches: List[str] = field(default_factory=list)
    evidence_of_uncertainty: List[str] = field(default_factory=list)


@dataclass
class AuditDefensePack:
    """Complete audit defense package for a project."""
    project_id: str
    project_name: str
    project_description: str
    
    # IRS Section 41 Analysis
    eligibility_determination: Dict[str, str]  # {criterion: status}
    
    # Executive Summary
    executive_summary: str
    
    # Technological Uncertainty
    technological_uncertainty: Optional[TechnologicalUncertainty] = None
    
    # Experimentation Evidence
    experimentation_evidence: List[ExperimentationEvidence] = field(default_factory=list)
    
    # Code Artifacts
    code_artifacts: List[CodeArtifact] = field(default_factory=list)
    
    # Team Contributions
    team_contributions: List[TeamContribution] = field(default_factory=list)
    
    # Additional Documentation
    design_documents: List[Dict[str, str]] = field(default_factory=list)  # [{title, url/filepath, summary}]
    test_results: List[Dict[str, str]] = field(default_factory=list)  # [{name, result, date}]
    decision_logs: List[Dict[str, str]] = field(default_factory=list)  # [{date, decision, rationale}]
    
    # Metadata
    generated_date: str = ""
    generator_version: str = "1.0"


class AuditDefenseGenerator:
    """Generate comprehensive audit defense pack."""
    
    def __init__(self):
        self.pack: Optional[AuditDefensePack] = None
    
    def create_executive_summary(
        self,
        project_name: str,
        project_description: str,
        key_rd_focus: str,
        uncertainty_snippet: str,
        total_qre: float,
    ) -> str:
        """Generate executive summary."""
        summary = (
            f"# Executive Summary - R&D Tax Credit Audit Defense\n\n"
            f"## Project: {project_name}\n\n"
            f"**Project Description:** {project_description}\n\n"
            f"**R&D Focus:** {key_rd_focus}\n\n"
            f"**Qualified Research Expenses (QRE):** ${total_qre:,.2f}\n\n"
            f"**Technological Uncertainty:** {uncertainty_snippet}\n\n"
            f"This document provides comprehensive evidence that {project_name} qualifies for "
            f"R&D tax credit under IRS Section 41. The project demonstrates all four required criteria: "
            f"(1) permitted purpose, (2) elimination of uncertainty, (3) process of experimentation, "
            f"and (4) technological in nature.\n"
        )
        return summary
    
    def generate(
        self,
        project_id: str,
        project_name: str,
        project_description: str,
        eligibility_determination: Dict[str, str],
        technological_uncertainty: Optional[TechnologicalUncertainty] = None,
        experimentation_evidence: Optional[List[ExperimentationEvidence]] = None,
        code_artifacts: Optional[List[CodeArtifact]] = None,
        team_contributions: Optional[List[TeamContribution]] = None,
        design_documents: Optional[List[Dict[str, str]]] = None,
        test_results: Optional[List[Dict[str, str]]] = None,
        decision_logs: Optional[List[Dict[str, str]]] = None,
        total_qre: float = 0.0,
    ) -> AuditDefensePack:
        """
        Generate complete audit defense pack.
        
        Args:
            project_id: Project identifier
            project_name: Human-readable project name
            project_description: High-level description
            eligibility_determination: Dict mapping criteria to status (e.g., {"permitted_purpose": "met"})
            technological_uncertainty: TechnologicalUncertainty object
            experimentation_evidence: List of ExperimentationEvidence objects
            code_artifacts: List of CodeArtifact objects
            team_contributions: List of TeamContribution objects
            design_documents: List of dicts with {title, url/filepath, summary}
            test_results: List of dicts with {name, result, date}
            decision_logs: List of dicts with {date, decision, rationale}
            total_qre: Total QRE for this project
        
        Returns:
            AuditDefensePack
        """
        # Generate executive summary
        uncertainty_snippet = "See Technological Uncertainty section for details."
        if technological_uncertainty:
            uncertainty_snippet = technological_uncertainty.problem_statement
        
        exec_summary = self.create_executive_summary(
            project_name,
            project_description,
            "See experimentation evidence below",
            uncertainty_snippet,
            total_qre,
        )
        
        # Create pack
        self.pack = AuditDefensePack(
            project_id=project_id,
            project_name=project_name,
            project_description=project_description,
            eligibility_determination=eligibility_determination,
            executive_summary=exec_summary,
            technological_uncertainty=technological_uncertainty,
            experimentation_evidence=experimentation_evidence or [],
            code_artifacts=code_artifacts or [],
            team_contributions=team_contributions or [],
            design_documents=design_documents or [],
            test_results=test_results or [],
            decision_logs=decision_logs or [],
            generated_date=datetime.utcnow().isoformat() + "Z",
        )
        
        return self.pack
    
    def to_json(self) -> Dict[str, Any]:
        """Export pack as JSON."""
        if not self.pack:
            raise RuntimeError("No pack generated. Call generate() first.")
        
        return {
            "project_id": self.pack.project_id,
            "project_name": self.pack.project_name,
            "project_description": self.pack.project_description,
            "generated_date": self.pack.generated_date,
            "generator_version": self.pack.generator_version,
            "irs_section_41_analysis": {
                "eligibility_determination": self.pack.eligibility_determination,
                "explanation": "All four criteria must be met for qualification."
            },
            "executive_summary": self.pack.executive_summary,
            "technological_uncertainty": (
                {
                    "problem_statement": self.pack.technological_uncertainty.problem_statement,
                    "uncertainty_type": self.pack.technological_uncertainty.uncertainty_type,
                    "alternative_approaches": self.pack.technological_uncertainty.alternative_approaches,
                    "evidence": self.pack.technological_uncertainty.evidence_of_uncertainty,
                } if self.pack.technological_uncertainty else None
            ),
            "experimentation_evidence": [
                {
                    "hypothesis": e.hypothesis,
                    "methodology": e.methodology,
                    "test_approach": e.test_approach,
                    "results_summary": e.results_summary,
                    "failure_or_learning": e.failure_or_learning,
                    "iteration_count": e.iteration_count,
                    "key_metrics": e.key_metrics,
                } for e in self.pack.experimentation_evidence
            ],
            "code_artifacts": [
                {
                    "repository": a.repository,
                    "commit_hash": a.commit_hash,
                    "commit_date": a.commit_date,
                    "commit_message": a.commit_message,
                    "author": a.author,
                    "file_path": a.file_path,
                    "lines_changed": a.lines_changed,
                    "description": a.description,
                } for a in self.pack.code_artifacts
            ],
            "team_contributions": [
                {
                    "name": t.name,
                    "role": t.role,
                    "estimated_hours": t.estimated_hours,
                    "contribution_area": t.contribution_area,
                    "start_date": t.start_date,
                    "end_date": t.end_date,
                    "key_decisions": t.key_decisions,
                } for t in self.pack.team_contributions
            ],
            "design_documents": self.pack.design_documents,
            "test_results": self.pack.test_results,
            "decision_logs": self.pack.decision_logs,
        }
    
    def to_markdown(self) -> str:
        """Export pack as Markdown for human review."""
        if not self.pack:
            raise RuntimeError("No pack generated. Call generate() first.")
        
        md = ""
        md += self.pack.executive_summary + "\n\n"
        
        # Eligibility Determination
        md += "## IRS Section 41 Analysis\n\n"
        for criterion, status in self.pack.eligibility_determination.items():
            md += f"- **{criterion}**: {status}\n"
        md += "\n"
        
        # Technological Uncertainty
        if self.pack.technological_uncertainty:
            tu = self.pack.technological_uncertainty
            md += "## Technological Uncertainty\n\n"
            md += f"**Problem:** {tu.problem_statement}\n\n"
            md += f"**Type of Uncertainty:** {tu.uncertainty_type}\n\n"
            if tu.alternative_approaches:
                md += "**Alternative Approaches Considered:**\n"
                for approach in tu.alternative_approaches:
                    md += f"- {approach}\n"
                md += "\n"
            if tu.evidence_of_uncertainty:
                md += "**Evidence of Uncertainty:**\n"
                for evidence in tu.evidence_of_uncertainty:
                    md += f"- {evidence}\n"
                md += "\n"
        
        # Experimentation Evidence
        if self.pack.experimentation_evidence:
            md += "## Evidence of Experimentation\n\n"
            for i, exp in enumerate(self.pack.experimentation_evidence, 1):
                md += f"### Experiment {i}\n\n"
                md += f"**Hypothesis:** {exp.hypothesis}\n\n"
                md += f"**Methodology:** {exp.methodology}\n\n"
                md += f"**Test Approach:** {exp.test_approach}\n\n"
                md += f"**Results:** {exp.results_summary}\n\n"
                md += f"**Learning:** {exp.failure_or_learning}\n\n"
                md += f"**Iterations:** {exp.iteration_count}\n\n"
                if exp.key_metrics:
                    md += "**Key Metrics:**\n"
                    for metric, value in exp.key_metrics.items():
                        md += f"- {metric}: {value}\n"
                    md += "\n"
        
        # Code Artifacts
        if self.pack.code_artifacts:
            md += "## Code Artifacts & Git History\n\n"
            for artifact in self.pack.code_artifacts:
                md += f"- **{artifact.repository}** ({artifact.commit_hash[:7]})\n"
                md += f"  - Date: {artifact.commit_date}\n"
                md += f"  - Author: {artifact.author}\n"
                md += f"  - Message: {artifact.commit_message}\n"
                if artifact.file_path:
                    md += f"  - File: {artifact.file_path}\n"
                md += f"  - Lines Changed: {artifact.lines_changed}\n\n"
        
        # Team Contributions
        if self.pack.team_contributions:
            md += "## Team Contributions\n\n"
            for team in self.pack.team_contributions:
                md += f"- **{team.name}** ({team.role})\n"
                md += f"  - Hours: {team.estimated_hours}\n"
                md += f"  - Area: {team.contribution_area}\n"
                md += f"  - Period: {team.start_date} to {team.end_date}\n"
                if team.key_decisions:
                    md += f"  - Key Decisions: {', '.join(team.key_decisions)}\n"
                md += "\n"
        
        # Design Documents
        if self.pack.design_documents:
            md += "## Design Documents\n\n"
            for doc in self.pack.design_documents:
                md += f"- **{doc.get('title', 'Untitled')}**\n"
                md += f"  - {doc.get('summary', 'No summary available')}\n\n"
        
        # Test Results
        if self.pack.test_results:
            md += "## Test Results\n\n"
            for test in self.pack.test_results:
                md += f"- {test.get('name')}: {test.get('result')} ({test.get('date')})\n"
            md += "\n"
        
        # Decision Logs
        if self.pack.decision_logs:
            md += "## Decision Log\n\n"
            for decision in self.pack.decision_logs:
                md += f"- **{decision.get('date')}**: {decision.get('decision')}\n"
                md += f"  - Rationale: {decision.get('rationale')}\n\n"
        
        return md
