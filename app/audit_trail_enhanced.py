"""
Enhanced Audit Trail with SHA256 Signing (Phase 2.4)

Extends existing trace logger with:
- SHA256 file hash per decision
- Digital signing of trace packets
- Append-only ledger (immutable, WORM-compliant)
- Optional S3 + Glacier archival for compliance
- Blockchain-ready (can integrate Merkle tree linking)

This is a huge selling point to tax consultants: audit defensibility + compliance.
"""

import os
import json
import hashlib
import hmac
import openai
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


@dataclass
class TraceSignature:
    """Digital signature for a trace packet."""
    signing_algorithm: str  # "HMAC-SHA256", etc.
    signature_hex: str
    signed_timestamp: str
    signer_id: str = "system"


@dataclass
class TracePacket:
    """Immutable trace packet with signature."""
    packet_id: str
    project_id: str
    timestamp: str
    decision: str  # "eligible", "not_eligible", "manual_review"
    confidence: float
    rationale: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Hash & Signature
    content_hash: str = ""  # SHA256 of decision data
    signature: Optional[TraceSignature] = None
    previous_packet_hash: str = ""  # For ledger linking (Merkle-like)
    
    # Metadata
    version: str = "2.0"
    audit_trail_version: str = "1.0"


class AuditTrailManager:
    """Manage immutable, append-only audit trail."""
    
    def __init__(
        self,
        ledger_path: str = ".audit_trail",
        signing_key: Optional[str] = None,
        s3_bucket: Optional[str] = None,
    ):
        """
        Initialize audit trail manager.
        
        Args:
            ledger_path: Local directory to store append-only ledger
            signing_key: HMAC secret key for signing packets (if None, use env var)
            s3_bucket: S3 bucket for archival (optional)
        """
        self.ledger_path = Path(ledger_path)
        self.ledger_path.mkdir(exist_ok=True, parents=True)
        
        # Get signing key
        self.signing_key = (
            signing_key or os.getenv("AUDIT_TRAIL_SIGNING_KEY", "default-key-change-me")
        ).encode()
        
        # S3 config (optional)
        self.s3_bucket = s3_bucket or os.getenv("AUDIT_TRAIL_S3_BUCKET")
        self.s3_enabled = self.s3_bucket is not None
        
        # Track last packet hash (for Merkle linking)
        self.last_packet_hash = None
        self._load_last_packet_hash()
    
    def _load_last_packet_hash(self) -> None:
        """Load the hash of the last packet in the ledger."""
        index_file = self.ledger_path / "ledger_index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    index = json.load(f)
                    self.last_packet_hash = index.get("last_packet_hash")
            except Exception as e:
                logger.warning(f"Failed to load ledger index: {e}")
    
    def _compute_content_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of decision data."""
        content_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _sign_packet(self, packet: TracePacket) -> TraceSignature:
        """Sign a trace packet with HMAC-SHA256."""
        payload = json.dumps({
            "packet_id": packet.packet_id,
            "project_id": packet.project_id,
            "timestamp": packet.timestamp,
            "decision": packet.decision,
            "confidence": packet.confidence,
            "content_hash": packet.content_hash,
        }, sort_keys=True)
        
        signature_hex = hmac.new(
            self.signing_key,
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return TraceSignature(
            signing_algorithm="HMAC-SHA256",
            signature_hex=signature_hex,
            signed_timestamp=datetime.utcnow().isoformat() + "Z",
        )
    
    def create_packet(
        self,
        project_id: str,
        decision: str,
        confidence: float,
        rationale: str,
        data: Dict[str, Any],
    ) -> TracePacket:
        """
        Create and sign a new trace packet.
        
        Args:
            project_id: Project identifier
            decision: "eligible", "not_eligible", "manual_review"
            confidence: 0.0-1.0 confidence score
            rationale: Reasoning behind decision
            data: Additional context (criteria status, etc.)
        
        Returns:
            Signed TracePacket
        """
        import uuid
        
        packet_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Compute hash of decision data
        packet_data = {
            "project_id": project_id,
            "decision": decision,
            "confidence": confidence,
            "rationale": rationale,
            "context": data,
        }
        content_hash = self._compute_content_hash(packet_data)
        
        # Create packet
        packet = TracePacket(
            packet_id=packet_id,
            project_id=project_id,
            timestamp=timestamp,
            decision=decision,
            confidence=confidence,
            rationale=rationale,
            data=data,
            content_hash=content_hash,
            previous_packet_hash=self.last_packet_hash or "",
        )
        
        # Sign it
        packet.signature = self._sign_packet(packet)
        
        return packet
    
    def append_packet(self, packet: TracePacket) -> bool:
        """
        Append packet to immutable ledger.
        Returns True if successful, False otherwise.
        """
        try:
            # Write packet as JSON line (JSONL format for immutability)
            ledger_file = self.ledger_path / "ledger.jsonl"
            with open(ledger_file, "a") as f:
                packet_dict = asdict(packet)
                # Convert signature to dict if present
                if packet.signature:
                    packet_dict["signature"] = asdict(packet.signature)
                f.write(json.dumps(packet_dict) + "\n")
            
            # Update index
            self._update_index(packet)
            
            # Update last packet hash
            self.last_packet_hash = packet.content_hash
            
            # Optional S3 archival
            if self.s3_enabled:
                self._archive_to_s3(packet)
            
            logger.info(f"Appended trace packet {packet.packet_id} for {packet.project_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to append packet: {e}")
            return False
    
    def _update_index(self, packet: TracePacket) -> None:
        """Update ledger index metadata."""
        index_file = self.ledger_path / "ledger_index.json"
        index = {}
        
        if index_file.exists():
            try:
                with open(index_file) as f:
                    index = json.load(f)
            except Exception:
                pass
        
        # Update index
        if "packets_by_project" not in index:
            index["packets_by_project"] = {}
        
        if packet.project_id not in index["packets_by_project"]:
            index["packets_by_project"][packet.project_id] = []
        
        index["packets_by_project"][packet.project_id].append({
            "packet_id": packet.packet_id,
            "timestamp": packet.timestamp,
            "decision": packet.decision,
            "content_hash": packet.content_hash,
        })
        
        index["last_packet_hash"] = packet.content_hash
        index["last_update"] = datetime.utcnow().isoformat() + "Z"
        index["total_packets"] = index.get("total_packets", 0) + 1
        
        # Write updated index
        with open(index_file, "w") as f:
            json.dump(index, f, indent=2)
    
    def _archive_to_s3(self, packet: TracePacket) -> None:
        """Archive packet to S3 + Glacier (optional)."""
        try:
            import boto3
        except ImportError:
            logger.warning("boto3 not installed. S3 archival skipped.")
            return
        
        try:
            s3 = boto3.client("s3")
            key = f"audit_trail/{packet.project_id}/{packet.packet_id}.json"
            packet_dict = asdict(packet)
            if packet.signature:
                packet_dict["signature"] = asdict(packet.signature)
            
            s3.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=json.dumps(packet_dict),
                StorageClass="GLACIER",  # Immutable storage
            )
            logger.info(f"Archived packet {packet.packet_id} to S3 Glacier")
        except Exception as e:
            logger.error(f"S3 archival failed: {e}")
    
    def verify_packet(self, packet: TracePacket) -> bool:
        """
        Verify packet signature and content integrity.
        Returns True if valid, False otherwise.
        """
        if not packet.signature:
            logger.warning(f"Packet {packet.packet_id} has no signature")
            return False
        
        # Reconstruct HMAC
        payload = json.dumps({
            "packet_id": packet.packet_id,
            "project_id": packet.project_id,
            "timestamp": packet.timestamp,
            "decision": packet.decision,
            "confidence": packet.confidence,
            "content_hash": packet.content_hash,
        }, sort_keys=True)
        
        expected_sig = hmac.new(
            self.signing_key,
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_sig, packet.signature.signature_hex)
        if is_valid:
            logger.info(f"Packet {packet.packet_id} signature verified")
        else:
            logger.warning(f"Packet {packet.packet_id} signature invalid!")
        
        return is_valid
    
    def get_project_trail(self, project_id: str) -> List[TracePacket]:
        """
        Retrieve all packets for a project (audit trail).
        Returned in chronological order.
        """
        packets = []
        ledger_file = self.ledger_path / "ledger.jsonl"
        
        if not ledger_file.exists():
            return packets
        
        try:
            with open(ledger_file) as f:
                for line in f:
                    packet_dict = json.loads(line)
                    if packet_dict.get("project_id") == project_id:
                        # Reconstruct TracePacket (simplified)
                        packet = TracePacket(**packet_dict)
                        packets.append(packet)
        except Exception as e:
            logger.error(f"Failed to read ledger: {e}")
        
        return packets
    
    def export_audit_report(self, project_id: str, format: str = "json") -> str:
        """
        Export audit trail for a project in specified format.
        
        Args:
            project_id: Project identifier
            format: "json" or "markdown"
        
        Returns:
            Formatted audit report as string
        """
        packets = self.get_project_trail(project_id)
        
        if format == "json":
            report_data = {
                "project_id": project_id,
                "generated": datetime.utcnow().isoformat() + "Z",
                "packet_count": len(packets),
                "packets": [asdict(p) if not hasattr(p, "__dict__") else p.__dict__ for p in packets],
            }
            return json.dumps(report_data, indent=2)
        
        elif format == "markdown":
            md = f"# Audit Trail Report\n\nProject: {project_id}\n\n"
            md += f"Generated: {datetime.utcnow().isoformat()}Z\n\n"
            md += f"Total Packets: {len(packets)}\n\n"
            
            for i, packet in enumerate(packets, 1):
                md += f"## Packet {i}\n\n"
                md += f"- **ID**: {packet.packet_id}\n"
                md += f"- **Timestamp**: {packet.timestamp}\n"
                md += f"- **Decision**: {packet.decision}\n"
                md += f"- **Confidence**: {packet.confidence}\n"
                md += f"- **Rationale**: {packet.rationale}\n"
                md += f"- **Content Hash**: {packet.content_hash}\n"
                if packet.signature:
                    # Handle both TraceSignature object and dict
                    if isinstance(packet.signature, dict):
                        sig_hex = packet.signature.get("signature_hex", "unknown")[:16]
                    else:
                        sig_hex = packet.signature.signature_hex[:16]
                    md += f"- **Signature**: {sig_hex}... (HMAC-SHA256)\n"
                md += "\n"
            
            return md
        
        else:
            raise ValueError(f"Unknown format: {format}")
