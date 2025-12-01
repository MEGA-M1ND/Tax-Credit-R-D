"""
Form 6765 Auto-Generation Module (Phase 2.2)

Generates IRS Form 6765 (Credit for Qualified Research Expenses):
- Part A: QRE Summary
- Part B: Regular Credit Calculation
- Part C: ASC Credit Calculation
- Part D: Other Information

Exports to JSON, CSV, and PDF (via reportlab).
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import csv
from io import StringIO

# -------------------------
# Constants
# -------------------------

class CreditType(Enum):
    REGULAR = "regular"
    ASC = "asc"
    BOTH = "both"


@dataclass
class GrossReceiptsPeriod:
    """Historical gross receipts data for a tax year."""
    year: int
    gross_receipts: float


@dataclass
class Form6765Data:
    """Complete Form 6765 filing data."""
    # Metadata
    project_id: str
    tax_year: int
    filing_status: str  # Individual, Corporation, etc.
    
    # Part A: QRE Summary
    wages: float
    supplies: float
    cloud_computing: float
    contract_research_65pct: float
    total_qre: float
    
    # Part B: Regular Credit
    regular_credit_rate: float = 0.20  # 20% base rate
    base_amount: float = 0.0
    fixed_base_percentage: float = 0.0
    regular_credit: float = 0.0
    
    # Part C: ASC Credit
    use_asc: bool = False
    asc_rate: float = 0.14  # 14%
    asc_base_amount: float = 0.0
    asc_credit: float = 0.0
    
    # Part D: Other Information
    num_employees: int = 0
    cloud_computing_disclosure: bool = False
    contract_research_disclosure: bool = False
    gross_receipts_history: List[GrossReceiptsPeriod] = None
    
    # Generated fields
    total_credit: float = 0.0
    timestamp: str = ""


class Form6765Generator:
    """Generate complete Form 6765 filing package."""
    
    def __init__(self):
        self.data: Optional[Form6765Data] = None
    
    def calculate_regular_credit(self, data: Form6765Data) -> float:
        """
        Calculate Part B: Regular Credit
        
        Regular Credit = (QRE - Base Amount) × 20%
        Base Amount = Average Gross Receipts × Fixed Base %
        """
        if not data.gross_receipts_history or len(data.gross_receipts_history) == 0:
            # Default: assume base amount is 0 if no historical data
            return data.total_qre * data.regular_credit_rate
        
        avg_gross_receipts = sum(p.gross_receipts for p in data.gross_receipts_history) / len(data.gross_receipts_history)
        data.base_amount = avg_gross_receipts * (data.fixed_base_percentage or 0.03)
        excess_qre = max(0, data.total_qre - data.base_amount)
        return excess_qre * data.regular_credit_rate
    
    def calculate_asc_credit(self, data: Form6765Data) -> float:
        """
        Calculate Part C: ASC (Alternative Simplified Credit)
        
        ASC Credit = QRE × 14%
        Limited to QRE from current year
        """
        if not data.use_asc:
            return 0.0
        
        data.asc_base_amount = data.total_qre
        return data.asc_base_amount * data.asc_rate
    
    def generate(
        self,
        project_id: str,
        tax_year: int,
        qre_data: Dict[str, float],
        gross_receipts_history: Optional[List[GrossReceiptsPeriod]] = None,
        use_asc: bool = False,
        num_employees: int = 0,
        filing_status: str = "Corporation",
    ) -> Form6765Data:
        """
        Generate Form 6765 data.
        
        Args:
            project_id: Project identifier
            tax_year: Tax year (e.g., 2024)
            qre_data: Dict with keys: wages, supplies, cloud_computing, contract_research_65pct
            gross_receipts_history: List of GrossReceiptsPeriod for base amount calculation
            use_asc: Whether to use Alternative Simplified Credit
            num_employees: Number of employees in company
            filing_status: Filing status
        
        Returns:
            Form6765Data with all calculations
        """
        data = Form6765Data(
            project_id=project_id,
            tax_year=tax_year,
            filing_status=filing_status,
            wages=qre_data.get("wages", 0.0),
            supplies=qre_data.get("supplies", 0.0),
            cloud_computing=qre_data.get("cloud_computing", 0.0),
            contract_research_65pct=qre_data.get("contract_research_65pct", 0.0),
            total_qre=sum(qre_data.values()),
            use_asc=use_asc,
            num_employees=num_employees,
            gross_receipts_history=gross_receipts_history or [],
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
        # Calculate credits
        data.regular_credit = self.calculate_regular_credit(data)
        data.asc_credit = self.calculate_asc_credit(data)
        
        # Choose greater credit (if both available)
        if use_asc:
            data.total_credit = max(data.regular_credit, data.asc_credit)
        else:
            data.total_credit = data.regular_credit
        
        self.data = data
        return data
    
    def to_json(self) -> Dict[str, Any]:
        """Export Form 6765 data as JSON."""
        if not self.data:
            raise RuntimeError("No data generated. Call generate() first.")
        
        return {
            "form_type": "6765",
            "tax_year": self.data.tax_year,
            "filing_status": self.data.filing_status,
            "project_id": self.data.project_id,
            "part_a_qre_summary": {
                "wages": self.data.wages,
                "supplies": self.data.supplies,
                "cloud_computing": self.data.cloud_computing,
                "contract_research_65pct": self.data.contract_research_65pct,
                "total_qre": self.data.total_qre,
            },
            "part_b_regular_credit": {
                "base_amount": self.data.base_amount,
                "fixed_base_percentage": self.data.fixed_base_percentage,
                "excess_qre": max(0, self.data.total_qre - self.data.base_amount),
                "credit_rate": self.data.regular_credit_rate,
                "total_regular_credit": self.data.regular_credit,
            },
            "part_c_asc_credit": {
                "use_asc": self.data.use_asc,
                "asc_rate": self.data.asc_rate,
                "asc_base": self.data.asc_base_amount,
                "total_asc_credit": self.data.asc_credit,
            },
            "part_d_other_information": {
                "num_employees": self.data.num_employees,
                "cloud_computing_disclosure": self.data.cloud_computing_disclosure,
                "contract_research_disclosure": self.data.contract_research_disclosure,
            },
            "total_credit": self.data.total_credit,
            "timestamp": self.data.timestamp,
        }
    
    def to_csv(self) -> str:
        """Export Form 6765 data as CSV."""
        if not self.data:
            raise RuntimeError("No data generated. Call generate() first.")
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["IRS Form 6765 - Credit for Qualified Research Expenses"])
        writer.writerow(["Tax Year", self.data.tax_year])
        writer.writerow(["Project ID", self.data.project_id])
        writer.writerow([])
        
        writer.writerow(["Part A: QRE Summary"])
        writer.writerow(["Category", "Amount"])
        writer.writerow(["Wages", self.data.wages])
        writer.writerow(["Supplies", self.data.supplies])
        writer.writerow(["Cloud Computing", self.data.cloud_computing])
        writer.writerow(["Contract Research (65%)", self.data.contract_research_65pct])
        writer.writerow(["TOTAL QRE", self.data.total_qre])
        writer.writerow([])
        
        writer.writerow(["Part B: Regular Credit"])
        writer.writerow(["Description", "Amount"])
        writer.writerow(["Base Amount", self.data.base_amount])
        writer.writerow(["Excess QRE", max(0, self.data.total_qre - self.data.base_amount)])
        writer.writerow(["Credit Rate", f"{self.data.regular_credit_rate*100}%"])
        writer.writerow(["Regular Credit", self.data.regular_credit])
        writer.writerow([])
        
        writer.writerow(["Part C: ASC Credit"])
        writer.writerow(["Description", "Amount"])
        writer.writerow(["Use ASC", self.data.use_asc])
        writer.writerow(["ASC Base", self.data.asc_base_amount])
        writer.writerow(["ASC Rate", f"{self.data.asc_rate*100}%"])
        writer.writerow(["ASC Credit", self.data.asc_credit])
        writer.writerow([])
        
        writer.writerow(["Part D: Other Information"])
        writer.writerow(["Number of Employees", self.data.num_employees])
        writer.writerow(["Cloud Computing Disclosure", self.data.cloud_computing_disclosure])
        writer.writerow(["Contract Research Disclosure", self.data.contract_research_disclosure])
        writer.writerow([])
        
        writer.writerow(["TOTAL CREDIT CLAIMED", self.data.total_credit])
        writer.writerow(["Generated", self.data.timestamp])
        
        return output.getvalue()
    
    def to_pdf(self, filepath: str) -> None:
        """
        Export Form 6765 data as PDF.
        Requires reportlab: pip install reportlab
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
        except ImportError:
            raise RuntimeError("PDF export requires reportlab. Install with: pip install reportlab")
        
        if not self.data:
            raise RuntimeError("No data generated. Call generate() first.")
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=20,
        )
        story.append(Paragraph("IRS Form 6765", title_style))
        story.append(Paragraph(f"Credit for Qualified Research Expenses - Tax Year {self.data.tax_year}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Part A
        story.append(Paragraph("Part A: QRE Summary", styles['Heading2']))
        part_a_data = [
            ["Category", "Amount"],
            ["Wages", f"${self.data.wages:,.2f}"],
            ["Supplies", f"${self.data.supplies:,.2f}"],
            ["Cloud Computing", f"${self.data.cloud_computing:,.2f}"],
            ["Contract Research (65%)", f"${self.data.contract_research_65pct:,.2f}"],
            ["TOTAL QRE", f"${self.data.total_qre:,.2f}"],
        ]
        part_a_table = Table(part_a_data)
        part_a_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(part_a_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Part B
        story.append(Paragraph("Part B: Regular Credit", styles['Heading2']))
        part_b_data = [
            ["Description", "Amount"],
            ["Base Amount", f"${self.data.base_amount:,.2f}"],
            ["Regular Credit", f"${self.data.regular_credit:,.2f}"],
        ]
        part_b_table = Table(part_b_data)
        part_b_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(part_b_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Part C
        story.append(Paragraph("Part C: ASC Credit", styles['Heading2']))
        part_c_data = [
            ["Description", "Amount"],
            ["ASC Credit", f"${self.data.asc_credit:,.2f}"],
        ]
        part_c_table = Table(part_c_data)
        part_c_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(part_c_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Total
        story.append(Paragraph(f"<b>Total Credit Claimed: ${self.data.total_credit:,.2f}</b>", styles['Normal']))
        
        doc.build(story)
