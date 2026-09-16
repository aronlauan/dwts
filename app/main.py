from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import ADMIN_KEY, ALLOWED_HIGHLIGHT_IMAGE_TYPES, FRONTEND_DIR, MAX_HIGHLIGHT_IMAGE_BYTES, UPLOADS_DIR
from app.db import Base, ensure_database_schema, engine, get_db
from app.models import Pairing, PickSheet, Season
from app.schemas import AdminLogin, EliminationCreate, HighlightYoutubeCreate, PairingCreate, PickSubmission, SeasonCreate, SiteMessageCreate, UserCreate
from app.services import (
    authenticate_admin,
    build_leaderboard,
    create_pick_sheet,
    create_user,
    get_highlight,
    get_season_eliminations,
    get_season_pick_averages,
    get_season_selection_views,
    get_site_message,
    is_pick_submission_locked,
    list_pairings_for_season,
    record_elimination,
    seed_pairings,
    serialize_highlight,
    update_highlight_image,
    update_highlight_youtube,
    update_site_message,
)

ensure_database_schema()

app = FastAPI(title="DWTS Picks")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"message": "DWTS Picks backend is running"}


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.post("/users")
def add_user(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = create_user(db, payload.username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": user.id, "username": user.username}


@app.post("/admin/login")
def admin_login(payload: AdminLogin):
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return {"admin_key": ADMIN_KEY, "username": payload.username}


@app.post("/seasons/bootstrap")
def bootstrap_season(payload: SeasonCreate | None = None, db: Session = Depends(get_db)):
    season_name = payload.name if payload else "DWTS 2026"
    season = seed_pairings(db, season_name=season_name)
    return {"id": season.id, "name": season.name}


@app.get("/seasons/{season_id}/pairings")
def get_pairings(season_id: int, db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")

    pairings = list_pairings_for_season(db, season_id)
    return [
        {"id": pairing.id, "star_name": pairing.star_name, "pro_name": pairing.pro_name}
        for pairing in pairings
    ]


@app.get("/deadline")
def get_deadline():
    return {"deadline": "2026-09-15T20:00:00-04:00", "timezone": "EDT"}


def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Admin access required")
    return x_admin_key


@app.get("/site-message")
def get_site_message_endpoint(db: Session = Depends(get_db)):
    message = get_site_message(db)
    return {"message": message.message}


@app.post("/site-message")
def update_site_message_endpoint(
    payload: SiteMessageCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    try:
        message = update_site_message(db, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": message.message}


@app.get("/highlight")
def get_highlight_endpoint(db: Session = Depends(get_db)):
    return serialize_highlight(get_highlight(db))


@app.get("/highlight/image")
def get_highlight_image_endpoint(db: Session = Depends(get_db)):
    highlight = get_highlight(db)
    if not highlight.image_data:
        raise HTTPException(status_code=404, detail="No highlight image is set")
    return Response(content=highlight.image_data, media_type=highlight.image_content_type or "application/octet-stream")


@app.post("/highlight/youtube")
def set_highlight_youtube_endpoint(
    payload: HighlightYoutubeCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    try:
        highlight = update_highlight_youtube(db, payload.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_highlight(highlight)


@app.post("/highlight/image")
async def set_highlight_image_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    if file.content_type not in ALLOWED_HIGHLIGHT_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Please upload a PNG, JPEG, WEBP, or GIF image")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(contents) > MAX_HIGHLIGHT_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be smaller than 5MB")

    # Stored as bytes in the database (not on disk) so it survives redeploys on hosts without persistent disks.
    highlight = update_highlight_image(db, contents, file.content_type)
    return serialize_highlight(highlight)


@app.post("/pick-sheets")
def submit_pick_sheet(payload: PickSubmission, db: Session = Depends(get_db)):
    if is_pick_submission_locked():
        raise HTTPException(status_code=403, detail="Selections are locked. The deadline passed on Tuesday, September 15 at 8:00 PM EDT.")
    try:
        sheet = create_pick_sheet(db, payload.name, payload.season_id, payload.predictions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"sheet_id": sheet.id, "name": sheet.player_name, "predictions": payload.predictions}


@app.post("/pairings")
def add_pairing(payload: PairingCreate, db: Session = Depends(get_db)):
    season = db.query(Season).first()
    if season is None:
        season = seed_pairings(db)
    return {"created": True, "season_id": season.id, "star": payload.star_name, "pro": payload.pro_name}


@app.post("/eliminations")
def add_elimination(
    payload: EliminationCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    season_id = payload.season_id
    if season_id is None:
        season = db.query(Season).order_by(Season.id.desc()).first()
        if season is None:
            raise HTTPException(status_code=404, detail="No active season found")
        season_id = season.id

    try:
        result = record_elimination(db, season_id, payload.star_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": result.id,
        "season_id": season_id,
        "star_name": payload.star_name,
        "elimination_order": result.elimination_order,
    }


@app.get("/seasons/{season_id}/pick-sheets")
def get_season_pick_sheets(season_id: int, db: Session = Depends(get_db)):
    try:
        selections = get_season_selection_views(db, season_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return selections


@app.get("/seasons/{season_id}/pick-averages")
def get_pick_averages(season_id: int, db: Session = Depends(get_db)):
    try:
        return get_season_pick_averages(db, season_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/leaderboard/{season_id}")
def get_leaderboard(season_id: int, db: Session = Depends(get_db)):
    try:
        leaderboard = build_leaderboard(db, season_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return leaderboard


@app.get("/seasons/{season_id}/eliminations")
def get_eliminations(season_id: int, db: Session = Depends(get_db)):
    try:
        eliminations = get_season_eliminations(db, season_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return eliminations


app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR), html=False), name="uploads")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=False), name="frontend")
