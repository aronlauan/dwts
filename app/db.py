from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import SQLALCHEMY_DATABASE_URL

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_database_schema():
    if engine.dialect.name != "sqlite":
        Base.metadata.create_all(bind=engine)
        return

    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='pick_sheets'")
        ).fetchone()

        if table_exists is None:
            Base.metadata.create_all(bind=engine)
            return

        columns = connection.execute(text("PRAGMA table_info(pick_sheets)")).fetchall()
        column_names = {row[1] for row in columns}
        user_id_not_null = any(row[1] == "user_id" and row[3] == 1 for row in columns)

        if "player_name" not in column_names or user_id_not_null:
            for index_name in ("ix_pick_sheets_id", "ix_pick_sheets_player_name", "uq_pick_sheet_season_name"):
                connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))

            legacy_exists = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='pick_sheets_legacy'")
            ).fetchone()
            if legacy_exists is not None:
                connection.execute(text("DROP TABLE pick_sheets_legacy"))

            connection.execute(text("ALTER TABLE pick_sheets RENAME TO pick_sheets_legacy"))
            connection.execute(
                text(
                    "CREATE TABLE pick_sheets ("
                    "id INTEGER PRIMARY KEY, "
                    "user_id INTEGER, "
                    "player_name VARCHAR NOT NULL, "
                    "season_id INTEGER NOT NULL, "
                    "FOREIGN KEY (user_id) REFERENCES users(id), "
                    "FOREIGN KEY (season_id) REFERENCES seasons(id)"
                    ")"
                )
            )

            rows = connection.execute(
                text("SELECT id, user_id, season_id FROM pick_sheets_legacy")
            ).fetchall()
            for legacy_id, user_id, season_id in rows:
                username = connection.execute(
                    text("SELECT username FROM users WHERE id = :user_id"),
                    {"user_id": user_id},
                ).scalar()
                player_name = username or f"Legacy Player {legacy_id}"
                connection.execute(
                    text(
                        "INSERT INTO pick_sheets (id, user_id, player_name, season_id) "
                        "VALUES (:id, :user_id, :player_name, :season_id)"
                    ),
                    {"id": legacy_id, "user_id": user_id, "player_name": player_name, "season_id": season_id},
                )

            connection.execute(text("DROP TABLE pick_sheets_legacy"))

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_pick_sheet_season_name "
                "ON pick_sheets (season_id, player_name)"
            )
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
