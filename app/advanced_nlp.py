"""
Advanced Eligibility NLP Features (Phase 3)

4.1 Project Decomposition: Break projects into research vs non-research components
4.2 Uncertainty Detector: Identify technical unknowns, experiments, failures
4.3 Experimentation Evidence Extractor: Extract specific experimentation phrases
"""

import json
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


# -------------------------
# Data Structures
# -------------------------

class ComponentType(Enum):
    """Type of project component."""
    RESEARCH = "research"                    # Eligible for R&D tax credit
    INFRASTRUCTURE = "infrastructure"        # Not eligible (deployment, DevOps)
    MAINTENANCE = "maintenance"              # Not eligible (bug fixes, routine updates)
    SUPPORT = "support"                      # Not eligible (documentation, training)
    BUSINESS = "business"                    # Not eligible (marketing, sales, HR)
    MIXED = "mixed"                          # Partially eligible (needs further analysis)


@dataclass
class ProjectComponent:
    """Individual component of a decomposed project."""
    name: str                                 # Short name
    description: str                          # Detailed description
    component_type: ComponentType
    estimated_percentage: float               # % of project effort
    rationale: str                            # Why this classification
    eligible: bool                            # True if research/eligible
    confidence: float                         # 0.0-1.0 confidence in classification
    subtasks: List[str] = field(default_factory=list)  # List of subtasks


@dataclass
class ProjectDecomposition:
    """Complete decomposition of a project."""
    project_id: str
    project_name: str
    total_components: int
    components: List[ProjectComponent]
    research_percentage: float                # % of project that is research
    eligible_percentage: float                # Weighted % eligible effort
    non_eligible_components: List[str]        # Names of ineligible components
    overall_eligibility: str                  # "eligible", "partially_eligible", "not_eligible"
    decomposition_confidence: float
    rationale: str


@dataclass
class UncertaintyIndicator:
    """Single uncertainty indicator detected."""
    indicator_type: str  # "technical_unknown", "experiment", "benchmark", "failure", "new_method"
    description: str
    confidence: float
    evidence_phrases: List[str]


@dataclass
class UncertaintyAnalysis:
    """Uncertainty detection results."""
    project_id: str
    has_technical_unknowns: bool
    has_experiments: bool
    has_benchmarks: bool
    has_failures: bool
    has_new_methods: bool
    overall_uncertainty_score: float          # 0.0-1.0
    indicators: List[UncertaintyIndicator] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)  # What evidence is missing
    rationale: str = ""


@dataclass
class ExperimentationPhrase:
    """Extracted experimentation evidence phrase."""
    phrase_type: str  # "architecture_comparison", "parameter_optimization", "alternative_approach", etc.
    quote: str        # Actual text from project description
    context: str      # Surrounding context (1-2 sentences)
    confidence: float


@dataclass
class ExperimentationEvidence:
    """Extracted experimentation evidence from project."""
    project_id: str
    total_phrases_found: int
    architecture_comparisons: List[ExperimentationPhrase] = field(default_factory=list)
    parameter_optimizations: List[ExperimentationPhrase] = field(default_factory=list)
    alternative_approaches: List[ExperimentationPhrase] = field(default_factory=list)
    testing_approaches: List[ExperimentationPhrase] = field(default_factory=list)
    failure_learnings: List[ExperimentationPhrase] = field(default_factory=list)
    hypotheses_tested: List[ExperimentationPhrase] = field(default_factory=list)
    all_phrases: List[ExperimentationPhrase] = field(default_factory=list)
    evidence_strength: str = "weak"  # "weak", "moderate", "strong"
    audit_ready_summary: str = ""


# -------------------------
# 4.1 Project Decomposer
# -------------------------

RESEARCH_KEYWORDS = {
    "algorithm", "ml", "ai", "prototype", "experimentation", "novel",
    "optimization", "performance", "uncertainty", "hypothesis", "architecture",
    "design", "model", "learning", "innovation", "new approach", "framework",
    "inference", "training", "neural", "deep learning", "research", "proof of concept"
}

INFRASTRUCTURE_KEYWORDS = {
    "deployment", "devops", "ci/cd", "docker", "kubernetes", "hosting",
    "cloud", "infrastructure", "provisioning", "monitoring", "logging",
    "ops", "production support", "release", "build"
}

MAINTENANCE_KEYWORDS = {
    "bug fix", "patch", "maintenance", "upgrade", "routine", "fix",
    "debug", "refactor", "cleanup", "technical debt", "legacy", "deprecat"
}

SUPPORT_KEYWORDS = {
    "documentation", "training", "onboarding", "wiki", "manual",
    "guide", "tutorial", "education", "knowledge base"
}

BUSINESS_KEYWORDS = {
    "marketing", "sales", "business development", "hr", "admin",
    "finance", "accounting", "compliance", "legal", "market research",
    "customer support", "operations", "management"
}


class ProjectDecomposer:
    """Break projects into research vs non-research components.

    Optional LLM support: pass an OpenAI sync client instance via `llm_client`
    and a `model_name` when constructing or calling `decompose_project(..., use_llm=True)`.
    """

    def __init__(self, llm_client: Optional[Any] = None, model_name: Optional[str] = None):
        """
        Initialize decomposer.

        Args:
            llm_client: Optional OpenAI client for LLM-based decomposition
            model_name: Optional model name string to use with the LLM client
        """
        self.llm_client = llm_client
        self.model_name = model_name
    
    def _keyword_classify(self, text: str) -> Tuple[ComponentType, float]:
        """
        Classify text using keyword matching (fast, no LLM).
        Returns (component_type, confidence).
        """
        text_l = (text or "").lower()
        
        # Count keyword matches
        research_score = sum(1 for kw in RESEARCH_KEYWORDS if kw in text_l)
        infra_score = sum(1 for kw in INFRASTRUCTURE_KEYWORDS if kw in text_l)
        maint_score = sum(1 for kw in MAINTENANCE_KEYWORDS if kw in text_l)
        support_score = sum(1 for kw in SUPPORT_KEYWORDS if kw in text_l)
        business_score = sum(1 for kw in BUSINESS_KEYWORDS if kw in text_l)
        
        scores = {
            ComponentType.RESEARCH: research_score,
            ComponentType.INFRASTRUCTURE: infra_score,
            ComponentType.MAINTENANCE: maint_score,
            ComponentType.SUPPORT: support_score,
            ComponentType.BUSINESS: business_score,
        }
        
        # Find max
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # If multiple high scores, mark as mixed
        high_scores = [s for s in scores.values() if s > 0]
        if len(high_scores) > 1 and max(high_scores) == scores[best_type]:
            confidence = best_score / (sum(scores.values()) + 0.01)
        else:
            confidence = 0.3 if best_score == 0 else 0.7
        
        return best_type, confidence
    
    def decompose_project(
        self,
        project_id: str,
        project_name: str,
        project_description: str,
        use_llm: bool = False,
    ) -> ProjectDecomposition:
        """
        Decompose project into research and non-research components.
        
        Args:
            project_id: Project identifier
            project_name: Project name
            project_description: Detailed description
            use_llm: Whether to use LLM for enhanced decomposition
        
        Returns:
            ProjectDecomposition with component breakdown
        """
        components = []
        
        # If LLM requested and available, attempt LLM-based decomposition first
        if use_llm and self.llm_client is not None and self.model_name:
            try:
                llm_result = self._llm_decompose(project_description)
                if llm_result and isinstance(llm_result, list):
                    # build components from LLM result
                    for item in llm_result:
                        try:
                            c_type = ComponentType(item.get("component_type", "mixed"))
                        except Exception:
                            c_type = ComponentType.MIXED
                        comp = ProjectComponent(
                            name=item.get("name", "Unnamed Component"),
                            description=item.get("description", ""),
                            component_type=c_type,
                            estimated_percentage=float(item.get("estimated_percentage", 0.0)),
                            rationale=item.get("rationale", "LLM-classified"),
                            eligible=bool(item.get("eligible", c_type == ComponentType.RESEARCH)),
                            confidence=float(item.get("confidence", 0.6)),
                            subtasks=item.get("subtasks", []),
                        )
                        components.append(comp)
                    # compute metrics
                    research_percentage = sum(c.estimated_percentage for c in components if c.eligible) / 100.0
                    eligible_percentage = sum(c.estimated_percentage * (1.0 if c.eligible else 0.0) for c in components) / 100.0
                    non_eligible = [c.name for c in components if not c.eligible]
                    if eligible_percentage >= 0.8:
                        overall_eligibility = "eligible"
                    elif eligible_percentage >= 0.5:
                        overall_eligibility = "partially_eligible"
                    else:
                        overall_eligibility = "not_eligible"
                    decomposition = ProjectDecomposition(
                        project_id=project_id,
                        project_name=project_name,
                        total_components=len(components),
                        components=components,
                        research_percentage=research_percentage,
                        eligible_percentage=eligible_percentage,
                        non_eligible_components=non_eligible,
                        overall_eligibility=overall_eligibility,
                        decomposition_confidence=0.85,
                        rationale="LLM-based decomposition",
                    )
                    return decomposition
            except Exception:
                # Fallback to keyword method below
                pass

        # If short description, treat as single component
        if len(project_description) < 200:
            component_type, conf = self._keyword_classify(project_description)
            component = ProjectComponent(
                name=project_name,
                description=project_description,
                component_type=component_type,
                estimated_percentage=100.0,
                rationale=f"Classified as {component_type.value} based on keywords",
                eligible=component_type == ComponentType.RESEARCH,
                confidence=conf,
            )
            components.append(component)
        else:
            # Split description into sentences and group into themes
            sentences = re.split(r'[.!?]+', project_description)
            
            # Simple heuristic: group consecutive sentences by topic
            current_component = None
            component_sentences = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                comp_type, conf = self._keyword_classify(sentence)
                
                # If different type, start new component
                if current_component is None or current_component != comp_type:
                    if current_component is not None and component_sentences:
                        # Save previous component
                        comp_desc = " ".join(component_sentences)
                        component = ProjectComponent(
                            name=f"{current_component.value.title()} Component",
                            description=comp_desc,
                            component_type=current_component,
                            estimated_percentage=len(component_sentences) / len(sentences) * 100,
                            rationale=f"Identified as {current_component.value}",
                            eligible=current_component == ComponentType.RESEARCH,
                            confidence=0.75,
                        )
                        components.append(component)
                    
                    current_component = comp_type
                    component_sentences = [sentence]
                else:
                    component_sentences.append(sentence)
            
            # Save last component
            if current_component is not None and component_sentences:
                comp_desc = " ".join(component_sentences)
                component = ProjectComponent(
                    name=f"{current_component.value.title()} Component",
                    description=comp_desc,
                    component_type=current_component,
                    estimated_percentage=len(component_sentences) / len(sentences) * 100,
                    rationale=f"Identified as {current_component.value}",
                    eligible=current_component == ComponentType.RESEARCH,
                    confidence=0.75,
                )
                components.append(component)
        
        # Calculate overall metrics
        research_percentage = sum(
            c.estimated_percentage for c in components if c.eligible
        ) / 100.0
        eligible_percentage = sum(
            c.estimated_percentage * (1.0 if c.eligible else 0.0) for c in components
        ) / 100.0
        
        non_eligible = [c.name for c in components if not c.eligible]
        
        # Determine overall eligibility
        if eligible_percentage >= 0.8:
            overall_eligibility = "eligible"
        elif eligible_percentage >= 0.5:
            overall_eligibility = "partially_eligible"
        else:
            overall_eligibility = "not_eligible"
        
        # Generate rationale
        rationale = (
            f"Project decomposed into {len(components)} components. "
            f"{eligible_percentage*100:.0f}% estimated as research/eligible. "
        )
        if non_eligible:
            rationale += f"Ineligible components: {', '.join(non_eligible)}."
        
        decomposition = ProjectDecomposition(
            project_id=project_id,
            project_name=project_name,
            total_components=len(components),
            components=components,
            research_percentage=research_percentage,
            eligible_percentage=eligible_percentage,
            non_eligible_components=non_eligible,
            overall_eligibility=overall_eligibility,
            decomposition_confidence=0.8,
            rationale=rationale,
        )
        
        return decomposition

    # -------------------------
    # LLM helpers (sync)
    # -------------------------
    def _safe_parse_json(self, content: str) -> Any:
        try:
            return json.loads(content)
        except Exception:
            m = re.search(r"\{.*\}|\[.*\]", content or "", re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return None
            return None

    def _llm_decompose(self, description: str) -> Optional[List[Dict[str, Any]]]:
        """Call the LLM to produce a JSON array of components.

        Expected JSON format (array of components):
        [{"name":"...","description":"...","component_type":"research","estimated_percentage":60.0,
          "rationale":"...","eligible":true,"confidence":0.85}]
        """
        if not (self.llm_client and self.model_name):
            return None
        msgs = [
            {"role": "system", "content": "You are an expert analyst who breaks a project description into discrete components and classifies each as research/infrastructure/maintenance/support/business. Return ONLY valid JSON array."},
            {"role": "user", "content": f"Project Description:\n{description}\n\nReturn JSON array of components with fields: name, description, component_type (research|infrastructure|maintenance|support|business|mixed), estimated_percentage (number), rationale (short), eligible (true|false), confidence (0.0-1.0)"}
        ]
        # Build params minimally; not all SDKs accept same args
        params = {"model": self.model_name, "messages": msgs, "temperature": 0, "max_tokens": 600}
        try:
            r = self.llm_client.chat.completions.create(**params)
            content = (r.choices[0].message.content or "").strip()
            parsed = self._safe_parse_json(content)
            return parsed if isinstance(parsed, list) else None
        except Exception:
            return None


# -------------------------
# 4.2 Uncertainty Detector
# -------------------------

UNCERTAINTY_PATTERNS = {
    "technical_unknown": [
        r"uncertain.*how|how.*uncertain",
        r"whether.*could|could.*whether",
        r"unknown.*approach|approach.*unknown",
        r"unclear.*method|method.*unclear",
        r"feasibility.*question|question.*feasibility",
    ],
    "experiment": [
        r"tested|test.*approach|experimented|experiment",
        r"tried.*multiple|multiple.*approach",
        r"evaluated.*option|option.*evaluat",
        r"compared.*architecture|architecture.*compar",
        r"a/b.*test|test.*variant",
    ],
    "benchmark": [
        r"benchmark|measure.*performance|performance.*metric",
        r"latency|throughput|accuracy.*test",
        r"performance.*target|target.*performance",
        r"baseline|compare.*baseline",
    ],
    "failure": [
        r"failed|failure|didn't.*work|didn't work",
        r"learned.*from|learned that",
        r"mistake|error.*discover",
        r"unexpected|surprising.*result",
    ],
    "new_method": [
        r"novel|new.*approach|approach.*new",
        r"developed.*method|method.*develop",
        r"invented|innovation|custom.*solution",
        r"unique|first.*time|for.*first.*time",
    ],
}


class UncertaintyDetector:
    """Detect technical uncertainty indicators in project descriptions."""
    
    def detect_uncertainties(self, project_description: str, use_llm: bool = False, llm_client: Optional[Any] = None, model_name: Optional[str] = None) -> UncertaintyAnalysis:
        """
        Detect uncertainty indicators in project description.
        
        Args:
            project_description: Project description text
        
        Returns:
            UncertaintyAnalysis with detected indicators
        """
        text = (project_description or "").lower()
        indicators = []

        # If LLM requested, attempt LLM-based detection
        if use_llm and llm_client and model_name:
            llm_res = self._llm_detect_uncertainties(project_description, llm_client, model_name)
            if llm_res:
                # Build indicators from llm_res
                indicators = []
                for it in llm_res.get("indicators", []):
                    indicators.append(UncertaintyIndicator(
                        indicator_type=it.get("indicator_type", "unknown"),
                        description=it.get("description", ""),
                        confidence=float(it.get("confidence", 0.7)),
                        evidence_phrases=it.get("evidence_phrases", []),
                    ))
                has_technical_unknowns = llm_res.get("has_technical_unknowns", False)
                has_experiments = llm_res.get("has_experiments", False)
                has_benchmarks = llm_res.get("has_benchmarks", False)
                has_failures = llm_res.get("has_failures", False)
                has_new_methods = llm_res.get("has_new_methods", False)
                overall_score = float(llm_res.get("overall_uncertainty_score", 0.0))
                missing = llm_res.get("missing_evidence", [])
                rationale = llm_res.get("rationale", "")
                return UncertaintyAnalysis(
                    project_id="",
                    has_technical_unknowns=has_technical_unknowns,
                    has_experiments=has_experiments,
                    has_benchmarks=has_benchmarks,
                    has_failures=has_failures,
                    has_new_methods=has_new_methods,
                    overall_uncertainty_score=overall_score,
                    indicators=indicators,
                    missing_evidence=missing,
                    rationale=rationale,
                )
        
        # Check each uncertainty type
        for indicator_type, patterns in UNCERTAINTY_PATTERNS.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                for match in matches:
                    # Extract surrounding context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    
                    indicator = UncertaintyIndicator(
                        indicator_type=indicator_type,
                        description=f"Detected: {match.group()}",
                        confidence=0.7,
                        evidence_phrases=[match.group()],
                    )
                    indicators.append(indicator)
        
        # Count by type
        has_technical_unknowns = any(i.indicator_type == "technical_unknown" for i in indicators)
        has_experiments = any(i.indicator_type == "experiment" for i in indicators)
        has_benchmarks = any(i.indicator_type == "benchmark" for i in indicators)
        has_failures = any(i.indicator_type == "failure" for i in indicators)
        has_new_methods = any(i.indicator_type == "new_method" for i in indicators)
        
        # Calculate overall uncertainty score
        uncertainty_count = len(indicators)
        overall_score = min(1.0, uncertainty_count / 10.0)  # Scale 0-1
        
        # Identify missing evidence
        missing = []
        if not has_technical_unknowns:
            missing.append("No clear technical uncertainty expressed")
        if not has_experiments:
            missing.append("No experiments or alternatives mentioned")
        if not has_benchmarks:
            missing.append("No performance benchmarks or metrics mentioned")
        if not has_failures:
            missing.append("No learning from failures documented")
        if not has_new_methods:
            missing.append("No new methods or novel approaches mentioned")
        
        # Generate rationale
        rationale = f"Detected {uncertainty_count} uncertainty indicators. "
        detected = []
        if has_technical_unknowns:
            detected.append("technical unknowns")
        if has_experiments:
            detected.append("experiments")
        if has_benchmarks:
            detected.append("benchmarks")
        if has_failures:
            detected.append("failures/learnings")
        if has_new_methods:
            detected.append("new methods")
        
        if detected:
            rationale += f"Evidence found for: {', '.join(detected)}. "
        if missing:
            rationale += f"Missing: {', '.join(missing[:2])}. "
        
        analysis = UncertaintyAnalysis(
            project_id="",
            has_technical_unknowns=has_technical_unknowns,
            has_experiments=has_experiments,
            has_benchmarks=has_benchmarks,
            has_failures=has_failures,
            has_new_methods=has_new_methods,
            overall_uncertainty_score=overall_score,
            indicators=indicators,
            missing_evidence=missing,
            rationale=rationale,
        )
        
        return analysis

    def _llm_detect_uncertainties(self, description: str, llm_client: Any, model_name: str) -> Optional[Dict[str, Any]]:
        msgs = [
            {"role": "system", "content": "You are an expert at identifying technical uncertainty and experimentation evidence in project descriptions. Return ONLY valid JSON."},
            {"role": "user", "content": (
                "Project Description:\n" + description + "\n\n"
                "Return JSON with keys: has_technical_unknowns (bool), has_experiments (bool), "
                "has_benchmarks (bool), has_failures (bool), has_new_methods (bool), "
                "overall_uncertainty_score (0.0-1.0), indicators (array of objects with fields: indicator_type, description, confidence, evidence_phrases), "
                "missing_evidence (array), rationale (string)."
            )}
        ]
        params = {"model": model_name, "messages": msgs, "temperature": 0, "max_tokens": 400}
        try:
            r = llm_client.chat.completions.create(**params)
            content = (r.choices[0].message.content or "").strip()
            parsed = None
            try:
                parsed = json.loads(content)
            except Exception:
                m = re.search(r"\{.*\}", content or "", re.S)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                    except Exception:
                        parsed = None
            return parsed
        except Exception:
            return None


# -------------------------
# 4.3 Experimentation Evidence Extractor
# -------------------------

EXPERIMENTATION_PATTERNS = {
    "architecture_comparison": [
        r"compared.*architecture|architecture.*compar",
        r"multiple.*architecture|architecture.*option",
        r"design.*alternative|alternative.*design",
        r"approach.*vs|versus.*approach",
    ],
    "parameter_optimization": [
        r"optimized.*parameter|parameter.*optim",
        r"tuned.*hyperparameter|hyperparameter.*tun",
        r"adjusted.*setting|setting.*adjust",
        r"grid.*search|search.*parameter",
    ],
    "alternative_approach": [
        r"tried.*approach|approach.*try",
        r"alternative.*method|method.*alternat",
        r"different.*strategy|strategy.*differ",
        r"multiple.*formulation|formulation.*multipla",
    ],
    "testing_approach": [
        r"tested.*strategy|strategy.*test",
        r"a/b.*test|test.*variant",
        r"benchmark.*compar|compar.*benchmark",
        r"evaluated.*metric|metric.*evaluat",
    ],
    "failure_learning": [
        r"initial.*fail|fail.*initial",
        r"learned.*from.*fail|fail.*we.*learn",
        r"first.*attempt.*failed|failed.*first",
        r"discovered.*issue|issue.*discov",
    ],
    "hypothesis_testing": [
        r"hypothesis.*test|test.*hypothesis",
        r"expected.*result|result.*expect",
        r"validate.*approach|approach.*validat",
        r"proof.*concept|concept.*proof",
    ],
}


class ExperimentationExtractor:
    """Extract specific experimentation evidence phrases."""
    
    def extract_evidence(
        self,
        project_id: str,
        project_description: str,
    ) -> ExperimentationEvidence:
        """
        Extract experimentation evidence phrases from project description.
        
        Args:
            project_id: Project identifier
            project_description: Project description
        
        Returns:
            ExperimentationEvidence with extracted phrases
        """
        text = (project_description or "")
        text_lower = text.lower()
        
        all_phrases = []
        evidence = ExperimentationEvidence(project_id=project_id, total_phrases_found=0)
        
        # Extract phrases for each category
        for phrase_type, patterns in EXPERIMENTATION_PATTERNS.items():
            phrases_list = []
            
            for pattern in patterns:
                matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                for match in matches:
                    # Extract surrounding context (2-3 sentences)
                    match_start = match.start()
                    match_end = match.end()
                    
                    # Find sentence boundaries
                    sent_start = text_lower.rfind(".", 0, match_start)
                    sent_start = sent_start + 1 if sent_start >= 0 else 0
                    
                    sent_end = text_lower.find(".", match_end)
                    sent_end = sent_end + 1 if sent_end >= 0 else len(text)
                    
                    context = text[sent_start:sent_end].strip()
                    quote = text[match_start:match_end].strip()
                    
                    phrase = ExperimentationPhrase(
                        phrase_type=phrase_type,
                        quote=quote,
                        context=context,
                        confidence=0.75,
                    )
                    phrases_list.append(phrase)
                    all_phrases.append(phrase)
            
            # Assign to appropriate field
            if phrase_type == "architecture_comparison":
                evidence.architecture_comparisons = phrases_list
            elif phrase_type == "parameter_optimization":
                evidence.parameter_optimizations = phrases_list
            elif phrase_type == "alternative_approach":
                evidence.alternative_approaches = phrases_list
            elif phrase_type == "testing_approach":
                evidence.testing_approaches = phrases_list
            elif phrase_type == "failure_learning":
                evidence.failure_learnings = phrases_list
            elif phrase_type == "hypothesis_testing":
                evidence.hypotheses_tested = phrases_list
        
        # Calculate summary
        evidence.all_phrases = all_phrases
        evidence.total_phrases_found = len(all_phrases)
        
        # Determine evidence strength
        if evidence.total_phrases_found >= 10:
            evidence.evidence_strength = "strong"
        elif evidence.total_phrases_found >= 5:
            evidence.evidence_strength = "moderate"
        else:
            evidence.evidence_strength = "weak"
        
        # Generate audit-ready summary
        summary_parts = []
        if evidence.architecture_comparisons:
            summary_parts.append(f"{len(evidence.architecture_comparisons)} architecture comparisons")
        if evidence.parameter_optimizations:
            summary_parts.append(f"{len(evidence.parameter_optimizations)} parameter optimizations")
        if evidence.alternative_approaches:
            summary_parts.append(f"{len(evidence.alternative_approaches)} alternative approaches")
        if evidence.testing_approaches:
            summary_parts.append(f"{len(evidence.testing_approaches)} testing approaches")
        if evidence.failure_learnings:
            summary_parts.append(f"{len(evidence.failure_learnings)} failure learnings")
        if evidence.hypotheses_tested:
            summary_parts.append(f"{len(evidence.hypotheses_tested)} hypotheses tested")
        
        evidence.audit_ready_summary = (
            f"Experimentation Evidence ({evidence.evidence_strength}): "
            f"{', '.join(summary_parts)}"
        )
        
        return evidence
