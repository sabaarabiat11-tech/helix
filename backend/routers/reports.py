from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/reports", tags=["reports"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


@router.get("")
def list_reports():
    if not REPORTS_DIR.exists():
        return []

    files = sorted(REPORTS_DIR.glob("weekly_report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": f.name,
            "modified": f.stat().st_mtime,
            "size_bytes": f.stat().st_size,
        }
        for f in files
    ]


@router.get("/{filename}")
def get_report(filename: str):
    # Filename must be a bare name with no path separators — no directory traversal.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = REPORTS_DIR / filename
    if not path.exists() or path.suffix != ".md":
        raise HTTPException(status_code=404, detail="Report not found")

    return {"filename": filename, "content": path.read_text(encoding="utf-8")}
