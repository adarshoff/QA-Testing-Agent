import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from agent import run_scan
from memory import init_db, get_user_history, get_scan
from report_generator import generate_pdf_report

try:
    init_db()
    print("Database initialized successfully")
except Exception as e:
    print(f"Database init warning: {e}")

app = FastAPI(
    title="QA Testing Agent API",
    description="Autonomous Visual QA Agent — Playwright + Gemini 2.5 Flash",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _camel(d):
    if isinstance(d, list):
        return [_camel(i) for i in d]
    if isinstance(d, dict):
        return {_to_camel(k): _camel(v) for k, v in d.items()}
    return d


def _clean_result(result: dict) -> dict:
    raw_screenshots = result.pop("screenshots", [])
    result.pop("visual_results", None)
    result.pop("figma_b64", None)
    result.pop("page_tokens", None)  # raw per-page samples; design_tokens is the aggregated, API-facing form
    result["screenshots_meta"] = [
        {k: v for k, v in s.items() if k != "screenshot"}
        for s in raw_screenshots
    ]
    return result


class ScanRequest(BaseModel):
    userId: str
    url: str
    figmaBase64: Optional[str] = None


@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/scan")
async def create_scan(body: ScanRequest):
    try:
        result = run_scan(
            user_id=body.userId,
            url=body.url,
            figma_b64=body.figmaBase64,
        )
        result = _clean_result(result)
        return JSONResponse(content=_camel(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/{scan_id}")
async def get_scan_detail(scan_id: str):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return JSONResponse(content=_camel(scan))


@app.get("/scan/{scan_id}/report")
async def download_report(scan_id: str):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    try:
        pdf_bytes = generate_pdf_report(scan)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="qa-testing-agent-{scan_id[:8]}.pdf"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@app.get("/history/{user_id}")
async def get_history(user_id: str):
    scans = get_user_history(user_id)
    return JSONResponse(content={"scans": _camel(scans)})


FRONTEND_DIST = os.getenv("FRONTEND_DIST")

if FRONTEND_DIST and os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
