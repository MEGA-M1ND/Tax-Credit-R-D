import json, zipfile, hashlib, io
from datetime import datetime
from typing import Dict

def _sha256_bytes(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()

def build_evidence_pack(
    run_id: str,
    form_pdf: bytes,
    qre_csv: bytes,
    narrative_md: str,
    traces_json: Dict
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{run_id}/narrative.md", narrative_md)
        z.writestr(f"{run_id}/form_6765.pdf", form_pdf)
        z.writestr(f"{run_id}/qre.csv", qre_csv)
        z.writestr(f"{run_id}/traces.json", json.dumps(traces_json, indent=2))

        manifest = {
            "run_id": run_id,
            "created_at": datetime.utcnow().isoformat()+"Z",
            "files": {
                "narrative.md": _sha256_bytes(narrative_md.encode()),
                "form_6765.pdf": _sha256_bytes(form_pdf),
                "qre.csv": _sha256_bytes(qre_csv),
                "traces.json": _sha256_bytes(json.dumps(traces_json).encode()),
            }
        }
        z.writestr(f"{run_id}/manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue()
