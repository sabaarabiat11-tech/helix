from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from database import export_to_csv, sync_from_csv

router = APIRouter(prefix="/api/export", tags=["export"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"


@router.get("/csv")
def export_csv():
    """The only CSV-writing path in the app — generates a fresh CSV FROM
    SQLite on demand. This is what makes CSV 'export-only': the pipeline's
    own linkedin_master.csv is never touched by this."""
    sync_from_csv()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = EXPORTS_DIR / f"helix_export_{timestamp}.csv"
    export_to_csv(dest)
    return FileResponse(dest, media_type="text/csv", filename=dest.name)
