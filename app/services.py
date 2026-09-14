import json
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME, CAST_DATA_PATH
from app.models import EliminationResult, Pairing, PickEntry, PickSheet, Season, SiteMessage, User

PICK_SUBMISSION_DEADLINE = "2026-09-15T20:00:00-05:00"


def is_pick_submission_locked() -> bool:
    deadline = datetime.fromisoformat(PICK_SUBMISSION_DEADLINE)
    return datetime.now(deadline.tzinfo) >= deadline


def seed_pairings(db: Session, season_name: str = "DWTS 2026") -> Season:
    season = db.query(Season).filter(Season.name == season_name).first()
    if season is None:
        season = Season(name=season_name)
        db.add(season)
        db.commit()
        db.refresh(season)

    if db.query(Pairing).filter(Pairing.season_id == season.id).count() == 0:
        with CAST_DATA_PATH.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        for star_name, pro_name in payload.get("pairings", {}).items():
            db.add(Pairing(season_id=season.id, star_name=star_name, pro_name=pro_name))

        db.commit()

    return season


def create_user(db: Session, username: str) -> User:
    username = username.strip()
    if not username:
        raise ValueError("Username is required")

    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise ValueError("Username is already in use")

    user = User(username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_admin(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def get_site_message(db: Session) -> SiteMessage:
    message = db.query(SiteMessage).first()
    if message is None:
        message = SiteMessage(message="Keep it glam, keep it bold, and bring your best picks.")
        db.add(message)
        db.commit()
        db.refresh(message)
    return message


def update_site_message(db: Session, message_text: str) -> SiteMessage:
    cleaned = (message_text or "").strip()
    if not cleaned:
        raise ValueError("Message is required")

    message = db.query(SiteMessage).first()
    if message is None:
        message = SiteMessage(message=cleaned)
        db.add(message)
    else:
        message.message = cleaned

    db.commit()
    db.refresh(message)
    return message


def list_pairings_for_season(db: Session, season_id: int):
    return (
        db.query(Pairing)
        .filter(Pairing.season_id == season_id)
        .order_by(Pairing.id.asc())
        .all()
    )


def create_pick_sheet(db: Session, player_name: str, season_id: int, predicted_order: List[str]) -> PickSheet:
    cleaned_name = (player_name or "").strip()
    if not cleaned_name:
        raise ValueError("Name is required")

    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    pairings_by_name = {
        pairing.star_name: pairing.id for pairing in list_pairings_for_season(db, season_id)
    }

    ordered_names = list(predicted_order)
    if len(ordered_names) != len(pairings_by_name):
        raise ValueError("Prediction list must include every pairing")

    if len(set(ordered_names)) != len(ordered_names):
        raise ValueError("Duplicate predictions are not allowed")

    missing = set(pairings_by_name) - set(ordered_names)
    if missing:
        raise ValueError(f"Missing predictions for: {sorted(missing)}")

    existing_sheet = (
        db.query(PickSheet)
        .filter(PickSheet.season_id == season_id, PickSheet.player_name == cleaned_name)
        .first()
    )
    if existing_sheet is not None:
        raise ValueError(f"A submission for {cleaned_name} already exists for this season")

    sheet = PickSheet(player_name=cleaned_name, season_id=season_id)
    db.add(sheet)
    db.commit()
    db.refresh(sheet)

    for position, star_name in enumerate(ordered_names, start=1):
        mapping_id = pairings_by_name[star_name]
        db.add(PickEntry(pick_sheet_id=sheet.id, pairing_id=mapping_id, predicted_position=position))

    db.commit()
    return sheet


def record_elimination(db: Session, season_id: int, star_name: str) -> EliminationResult:
    pairing = (
        db.query(Pairing)
        .filter(Pairing.season_id == season_id, Pairing.star_name == star_name)
        .first()
    )
    if pairing is None:
        raise ValueError(f"No pairing found for {star_name}")

    if (
        db.query(EliminationResult)
        .filter(EliminationResult.season_id == season_id, EliminationResult.pairing_id == pairing.id)
        .first()
    ):
        raise ValueError(f"{star_name} has already been recorded as eliminated")

    current_count = db.query(EliminationResult).filter(EliminationResult.season_id == season_id).count()
    result = EliminationResult(season_id=season_id, pairing_id=pairing.id, elimination_order=current_count + 1)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def compute_points_for_pick(db: Session, pick_sheet_id: int, season_id: int) -> int:
    picks = db.query(PickEntry).filter(PickEntry.pick_sheet_id == pick_sheet_id).all()
    actuals = {
        entry.pairing_id: entry.elimination_order
        for entry in db.query(EliminationResult).filter(EliminationResult.season_id == season_id).all()
    }

    total = 0
    for pick in picks:
        real_order = actuals.get(pick.pairing_id)
        if real_order is None:
            continue
        distance = abs(pick.predicted_position - real_order)
        if distance == 0:
            total += 15
        elif distance == 1:
            total += 8
        elif distance == 2:
            total += 4
    return total


def get_season_selection_views(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    sheets = db.query(PickSheet).filter(PickSheet.season_id == season_id).all()
    selections = []

    for sheet in sheets:
        ranked = {}
        for entry in db.query(PickEntry).filter(PickEntry.pick_sheet_id == sheet.id).order_by(PickEntry.predicted_position.asc()).all():
            pairing = db.query(Pairing).filter(Pairing.id == entry.pairing_id).first()
            if pairing is not None:
                ranked[entry.predicted_position] = {"star_name": pairing.star_name, "pro_name": pairing.pro_name}

        ordered_predictions = [ranked[position]["star_name"] for position in sorted(ranked.keys())]
        selections.append({
            "sheet_id": sheet.id,
            "player_name": sheet.player_name,
            "predictions": ordered_predictions,
        })

    selections.sort(key=lambda item: item["player_name"].lower())
    return selections


def build_leaderboard(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    sheets = db.query(PickSheet).filter(PickSheet.season_id == season_id).all()
    standings = []

    for sheet in sheets:
        points = compute_points_for_pick(db, sheet.id, season_id)
        exact = 0
        for entry in db.query(PickEntry).filter(PickEntry.pick_sheet_id == sheet.id).all():
            actual_order = (
                db.query(EliminationResult)
                .filter(EliminationResult.season_id == season_id, EliminationResult.pairing_id == entry.pairing_id)
                .first()
            )
            if actual_order and entry.predicted_position == actual_order.elimination_order:
                exact += 1

        standings.append(
            {
                "sheet_id": sheet.id,
                "player_name": sheet.player_name,
                "points": points,
                "exact": exact,
            }
        )

    standings.sort(key=lambda item: (-item["points"], -item["exact"], item["player_name"]))
    for index, item in enumerate(standings, start=1):
        item["rank"] = index
    return standings
