import json
import re
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME, CAST_DATA_PATH, DEFAULT_HIGHLIGHT_IMAGE_URL
from app.models import EliminationResult, Highlight, Pairing, PickEntry, PickSheet, Season, SiteMessage, User

YOUTUBE_VIDEO_ID_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
]

PICK_SUBMISSION_DEADLINE = "2026-09-15T20:00:00-04:00"


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


def extract_youtube_video_id(url: str) -> str:
    cleaned = (url or "").strip()
    for pattern in YOUTUBE_VIDEO_ID_PATTERNS:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)
    raise ValueError("Could not find a valid YouTube video in that link")


def get_highlight(db: Session) -> Highlight:
    highlight = db.query(Highlight).first()
    if highlight is None:
        highlight = Highlight(media_type="image", image_filename=None, youtube_video_id=None)
        db.add(highlight)
        db.commit()
        db.refresh(highlight)
    return highlight


def serialize_highlight(highlight: Highlight) -> dict:
    if highlight.media_type == "youtube" and highlight.youtube_video_id:
        return {"type": "youtube", "youtube_video_id": highlight.youtube_video_id, "image_url": None}

    if highlight.image_data:
        # image_filename doubles as a cache-busting version token here, not a real path.
        image_url = f"/highlight/image?v={highlight.image_filename}"
    elif highlight.image_filename:
        image_url = f"/uploads/{highlight.image_filename}"
    else:
        image_url = f"/{DEFAULT_HIGHLIGHT_IMAGE_URL}"
    return {"type": "image", "image_url": image_url, "youtube_video_id": None}


def update_highlight_youtube(db: Session, youtube_url: str) -> Highlight:
    video_id = extract_youtube_video_id(youtube_url)
    highlight = get_highlight(db)
    highlight.media_type = "youtube"
    highlight.youtube_video_id = video_id
    db.commit()
    db.refresh(highlight)
    return highlight


def update_highlight_image(db: Session, content: bytes, content_type: str) -> Highlight:
    highlight = get_highlight(db)
    highlight.media_type = "image"
    highlight.image_data = content
    highlight.image_content_type = content_type
    highlight.image_filename = uuid.uuid4().hex
    db.commit()
    db.refresh(highlight)
    return highlight


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


def get_rank_multiplier(actual_rank: int) -> float:
    """
    Tier-based multipliers:
    - Winner (1st Place): 3.0x
    - Podium (Places 2 and 3): 2.0x
    - Semifinals (Places 4-6): 1.5x
    - Places 7+: 1.0x (Preserves base scoring for initial & mid eliminations)
    """
    if actual_rank == 1:
        return 3.0
    elif actual_rank <= 3:
        return 2.0
    elif actual_rank <= 6:
        return 1.5
    return 1.0


def compute_score_for_distance(distance: int, actual_rank: int = 7) -> int:
    if distance == 0:
        base = 15
    elif distance == 1:
        base = 8
    elif distance == 2:
        base = 4
    else:
        return 0
    return round(base * get_rank_multiplier(actual_rank))


def compute_score_for_pick(predicted_position: int, actual_rank: int) -> int:
    return compute_score_for_distance(abs(predicted_position - actual_rank), actual_rank)


def solve_max_weight_assignment(weights: List[List[int]]) -> int:
    """
    Finds the maximum weight matching in a bipartite graph represented by
    an m x n weight matrix using the Hungarian algorithm (Kuhn-Munkres).
    Handles non-square matrices by zero-padding.
    """
    if not weights or not weights[0]:
        return 0
    nrows = len(weights)
    ncols = len(weights[0])
    n = max(nrows, ncols)
    if n == 0:
        return 0
    if n == 1:
        return weights[0][0] if nrows > 0 and ncols > 0 else 0

    max_w = max((max(row) for row in weights), default=0)
    cost = [[0] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(n):
            val = weights[i][j] if (i < nrows and j < ncols) else 0
            cost[i + 1][j + 1] = max_w - val

    u = [0] * (n + 1)
    v = [0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0][j] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    total_weight = 0
    for j in range(1, n + 1):
        row = p[j] - 1
        col = j - 1
        if row < nrows and col < ncols:
            total_weight += weights[row][col]
    return total_weight


def compute_max_points_for_sheet(
    entries: List[PickEntry],
    actual_ranks: dict,
    total_pairings: int,
) -> tuple[int, int, int]:
    """
    Computes (current_points, exact_matches, max_points_available) for a pick sheet.
    Accounts for already eliminated pairings with tier-weighted scoring (1st place at 3.0x,
    places 2-3 at 2.0x, places 4-6 at 1.5x, places 7+ at 1.0x) and calculates the maximum
    possible points achievable across all valid permutations of remaining ranks for
    remaining pairings.
    """
    points = 0
    exact = 0
    active_entries: List[PickEntry] = []
    eliminated_ranks = set(actual_ranks.values())
    available_ranks = [r for r in range(1, total_pairings + 1) if r not in eliminated_ranks]

    for entry in entries:
        actual_rank = actual_ranks.get(entry.pairing_id)
        if actual_rank is not None:
            distance = abs(entry.predicted_position - actual_rank)
            score = compute_score_for_pick(entry.predicted_position, actual_rank)
            points += score
            if distance == 0:
                exact += 1
        else:
            active_entries.append(entry)

    if not active_entries or not available_ranks:
        max_remaining = 0
    else:
        weights = []
        for entry in active_entries:
            row = []
            for rank in available_ranks:
                score = compute_score_for_pick(entry.predicted_position, rank)
                row.append(score)
            weights.append(row)
        max_remaining = solve_max_weight_assignment(weights)

    return points, exact, points + max_remaining


def compute_points_for_pick(db: Session, pick_sheet_id: int, season_id: int) -> int:
    picks = db.query(PickEntry).filter(PickEntry.pick_sheet_id == pick_sheet_id).all()
    total_pairings = db.query(Pairing).filter(Pairing.season_id == season_id).count()
    actuals = {
        entry.pairing_id: total_pairings - entry.elimination_order + 1
        for entry in db.query(EliminationResult).filter(EliminationResult.season_id == season_id).all()
    }
    points, _, _ = compute_max_points_for_sheet(picks, actuals, total_pairings)
    return points


def compute_max_points_for_pick(db: Session, pick_sheet_id: int, season_id: int) -> int:
    picks = db.query(PickEntry).filter(PickEntry.pick_sheet_id == pick_sheet_id).all()
    total_pairings = db.query(Pairing).filter(Pairing.season_id == season_id).count()
    actuals = {
        entry.pairing_id: total_pairings - entry.elimination_order + 1
        for entry in db.query(EliminationResult).filter(EliminationResult.season_id == season_id).all()
    }
    _, _, max_points = compute_max_points_for_sheet(picks, actuals, total_pairings)
    return max_points


def get_season_selection_views(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    pairings = list_pairings_for_season(db, season_id)
    pairings_by_id = {pairing.id: pairing for pairing in pairings}
    total_pairings = len(pairings)
    actual_eliminations = {
        item.pairing_id: total_pairings - item.elimination_order + 1
        for item in db.query(EliminationResult).filter(EliminationResult.season_id == season_id).all()
    }

    sheets = db.query(PickSheet).filter(PickSheet.season_id == season_id).all()
    sheet_ids = [sheet.id for sheet in sheets]
    entries_by_sheet = {sheet_id: [] for sheet_id in sheet_ids}
    if sheet_ids:
        entries = (
            db.query(PickEntry)
            .filter(PickEntry.pick_sheet_id.in_(sheet_ids))
            .order_by(PickEntry.pick_sheet_id.asc(), PickEntry.predicted_position.asc())
            .all()
        )
        for entry in entries:
            entries_by_sheet[entry.pick_sheet_id].append(entry)

    selections = []

    for sheet in sheets:
        ranked = {}

        for entry in entries_by_sheet[sheet.id]:
            pairing = pairings_by_id.get(entry.pairing_id)
            if pairing is None:
                continue

            actual_order = actual_eliminations.get(pairing.id)
            ranked[entry.predicted_position] = {
                "position": entry.predicted_position,
                "star_name": pairing.star_name,
                "pro_name": pairing.pro_name,
                "is_eliminated": actual_order is not None,
                "elimination_order": actual_order,
                "status": "out" if actual_order is not None else "alive",
            }

        ordered_predictions = [ranked[position]["star_name"] for position in sorted(ranked.keys())]
        prediction_rows = [ranked[position] for position in sorted(ranked.keys())]
        selections.append({
            "sheet_id": sheet.id,
            "player_name": sheet.player_name,
            "predictions": ordered_predictions,
            "prediction_rows": prediction_rows,
        })

    selections.sort(key=lambda item: item["player_name"].lower())
    return selections


def get_season_pick_averages(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    pairings = list_pairings_for_season(db, season_id)
    sheets = db.query(PickSheet).filter(PickSheet.season_id == season_id).all()
    sheet_ids = [sheet.id for sheet in sheets]
    positions_by_pairing = {pairing.id: [] for pairing in pairings}

    if sheet_ids:
        entries = db.query(PickEntry).filter(PickEntry.pick_sheet_id.in_(sheet_ids)).all()
        for entry in entries:
            positions_by_pairing.setdefault(entry.pairing_id, []).append(entry.predicted_position)

    averages = []
    for pairing in pairings:
        positions = positions_by_pairing.get(pairing.id, [])
        if not positions:
            continue
        averages.append({
            "star_name": pairing.star_name,
            "pro_name": pairing.pro_name,
            "average_position": round(sum(positions) / len(positions), 1),
            "pick_count": len(positions),
        })

    averages.sort(key=lambda item: (item["average_position"], item["star_name"].lower()))
    return averages


def get_season_eliminations(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    total_pairings = db.query(Pairing).filter(Pairing.season_id == season_id).count()
    results = (
        db.query(EliminationResult)
        .filter(EliminationResult.season_id == season_id)
        .order_by(EliminationResult.elimination_order.asc())
        .all()
    )

    timeline = []
    for result in results:
        pairing = db.query(Pairing).filter(Pairing.id == result.pairing_id).first()
        if pairing is None:
            continue
        timeline.append({
            "elimination_order": result.elimination_order,
            "place_finished": total_pairings - result.elimination_order + 1,
            "star_name": pairing.star_name,
            "pro_name": pairing.pro_name,
        })
    return timeline


def build_leaderboard(db: Session, season_id: int):
    season = db.query(Season).filter(Season.id == season_id).first()
    if season is None:
        raise ValueError("Season does not exist")

    sheets = db.query(PickSheet).filter(PickSheet.season_id == season_id).all()
    standings = []

    total_pairings = db.query(Pairing).filter(Pairing.season_id == season_id).count()
    actual_ranks = {
        result.pairing_id: total_pairings - result.elimination_order + 1
        for result in db.query(EliminationResult).filter(EliminationResult.season_id == season_id).all()
    }
    sheet_ids = [sheet.id for sheet in sheets]
    entries_by_sheet = {sheet_id: [] for sheet_id in sheet_ids}
    if sheet_ids:
        for entry in db.query(PickEntry).filter(PickEntry.pick_sheet_id.in_(sheet_ids)).all():
            entries_by_sheet[entry.pick_sheet_id].append(entry)

    for sheet in sheets:
        sheet_entries = entries_by_sheet.get(sheet.id, [])
        points, exact, max_points = compute_max_points_for_sheet(
            entries=sheet_entries,
            actual_ranks=actual_ranks,
            total_pairings=total_pairings,
        )

        standings.append(
            {
                "sheet_id": sheet.id,
                "player_name": sheet.player_name,
                "points": points,
                "exact": exact,
                "max_points": max_points,
                "max_points_available": max_points,
            }
        )

    standings.sort(key=lambda item: (-item["points"], -item["exact"], -item["max_points"], item["player_name"]))
    for index, item in enumerate(standings, start=1):
        item["rank"] = index
    return standings
