import os
import json
import hashlib
import uuid
import pathlib
from typing import Dict, Any
from datetime import datetime

from cryptography.fernet import Fernet

TRACES_DIR = os.environ.get(
    "TRACE_DIR",
    str(pathlib.Path(__file__).resolve().parents[1] / "traces")
)

TRACE_ENCRYPT_KEY = os.getenv("TRACE_ENCRYPT_KEY")
_fernet = Fernet(TRACE_ENCRYPT_KEY) if TRACE_ENCRYPT_KEY else None


class ImmutableTraceLogger:
    """
    A simple WORM-like trace logger with optional encryption.

    - Writes new trace files; refuses to overwrite an existing path.
    - Computes and stores SHA-256 checksum for tamper-evidence.
    - If TRACE_ENCRYPT_KEY is set, encrypts the JSON payload at rest.
    """

    def __init__(self, base_dir: str = TRACES_DIR):
        os.makedirs(base_dir, exist_ok=True)
        self.base_dir = base_dir

    def _checksum(self, payload: dict) -> str:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _unique_path(self, project_id: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        uid = uuid.uuid4().hex[:8]
        fname = f"trace_{project_id}_{ts}_{uid}.json"
        return os.path.join(self.base_dir, fname)

    def write_trace(self, envelope: Dict[str, Any]) -> str:
        # compute checksum before writing
        checksum = self._checksum(envelope)
        envelope["checksum_sha256"] = checksum
        path = self._unique_path(envelope.get("project_id", "unknown"))

        # enforce WORM-like behavior
        if os.path.exists(path):
            raise FileExistsError("Trace path already exists; refusing to overwrite (WORM).")

        data = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")
        if _fernet:
            data = _fernet.encrypt(data)

        with open(path, "wb") as f:
            f.write(data)

        return path

    def verify(self, path: str) -> bool:
        with open(path, "rb") as f:
            raw = f.read()

        if _fernet:
            raw = _fernet.decrypt(raw)

        data = json.loads(raw.decode("utf-8"))
        saved = data.get("checksum_sha256", "")
        data_no_checksum = dict(data)
        data_no_checksum.pop("checksum_sha256", None)
        current = self._checksum(data_no_checksum)
        return saved == current