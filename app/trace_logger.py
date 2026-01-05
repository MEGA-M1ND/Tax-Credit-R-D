import os, json, hashlib, uuid, pathlib
from typing import Dict, Any, Optional
from datetime import datetime

TRACES_DIR = os.environ.get(
    "TRACE_DIR",
    str(pathlib.Path(__file__).resolve().parents[1] / "traces")
)

def _sanitize(s: str) -> str:
    return "".join(c for c in (s or "unknown") if c.isalnum() or c in ("-", "_")) or "unknown"

class ImmutableTraceLogger:
    """
    WORM-like trace logger with collision-proof filenames.
    - Microsecond timestamps + UUID
    - Atomic create (O_EXCL) to prevent overwrite
    """
    def __init__(self, base_dir: str = TRACES_DIR):
        os.makedirs(base_dir, exist_ok=True)
        self.base_dir = base_dir

    def _checksum(self, payload: dict) -> str:
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _unique_path(self, project_id: str, filename: Optional[str] = None) -> str:
        if filename:
            return os.path.join(self.base_dir, filename)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        uid = uuid.uuid4().hex[:8]
        pid = _sanitize(project_id)
        fname = f"trace_{pid}_{ts}_{uid}.json"
        return os.path.join(self.base_dir, fname)

    def write_trace(self, envelope: Dict[str, Any], filename: Optional[str] = None) -> str:
        envelope = dict(envelope)
        envelope["checksum_sha256"] = self._checksum(envelope)

        # Try a few times in the extremely unlikely case of collision
        for _ in range(5):
            path = self._unique_path(envelope.get("project_id", "unknown"), filename=filename)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            try:
                fd = os.open(path, flags)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(envelope, f, ensure_ascii=False, indent=2)
                except Exception:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass
                    raise
                return path
            except FileExistsError:
                # Try again with a new generated name (if filename wasn't forced)
                if filename:
                    raise
                continue

        raise FileExistsError("Trace file collision after multiple attempts (WORM).")

    def verify(self, path: str) -> bool:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        saved = data.get("checksum_sha256", "")
        payload = dict(data)
        payload.pop("checksum_sha256", None)
        return saved == self._checksum(payload)

    def write_review_trace(
        self,
        project_id: str,
        reviewer_name: str,
        reviewer_role: str,
        old_status: str,
        new_status: str,
        reason: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Write a trace for a review action.
        
        Args:
            project_id: Project being reviewed
            reviewer_name: Name of reviewer
            reviewer_role: Role of reviewer
            old_status: Previous status
            new_status: New status
            reason: Reason for action
            additional_data: Any extra data to include
        
        Returns:
            Path to the written trace file
        """
        envelope = {
            "type": "review_action",
            "timestamp": datetime.utcnow().isoformat(),
            "project_id": project_id,
            "reviewer_name": reviewer_name,
            "reviewer_role": reviewer_role,
            "action": {
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
            },
        }
        
        if additional_data:
            envelope.update(additional_data)
        
        return self.write_trace(envelope)
