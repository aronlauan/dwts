from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False, default="")
    password_salt = Column(String, nullable=False, default="")
    role = Column(String, nullable=False, default="user")

    pick_sheets = relationship("PickSheet", back_populates="user")


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    pairings = relationship("Pairing", back_populates="season")
    pick_sheets = relationship("PickSheet", back_populates="season")
    eliminations = relationship("EliminationResult", back_populates="season")


class SiteMessage(Base):
    __tablename__ = "site_messages"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String, nullable=False, default="Welcome to the DWTS Picks League!")


class Pairing(Base):
    __tablename__ = "pairings"

    id = Column(Integer, primary_key=True, index=True)
    star_name = Column(String, nullable=False)
    pro_name = Column(String, nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)

    season = relationship("Season", back_populates="pairings")
    pick_entries = relationship("PickEntry", back_populates="pairing")
    elimination_results = relationship("EliminationResult", back_populates="pairing")

    __table_args__ = (
        UniqueConstraint("season_id", "star_name", name="uq_pairing_season_star"),
    )


class PickSheet(Base):
    __tablename__ = "pick_sheets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player_name = Column(String, nullable=False, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)

    user = relationship("User", back_populates="pick_sheets")
    season = relationship("Season", back_populates="pick_sheets")
    entries = relationship("PickEntry", back_populates="pick_sheet")

    __table_args__ = (
        UniqueConstraint("season_id", "player_name", name="uq_pick_sheet_season_name"),
    )


class PickEntry(Base):
    __tablename__ = "pick_entries"

    id = Column(Integer, primary_key=True, index=True)
    pick_sheet_id = Column(Integer, ForeignKey("pick_sheets.id"), nullable=False)
    pairing_id = Column(Integer, ForeignKey("pairings.id"), nullable=False)
    predicted_position = Column(Integer, nullable=False)

    pick_sheet = relationship("PickSheet", back_populates="entries")
    pairing = relationship("Pairing", back_populates="pick_entries")


class EliminationResult(Base):
    __tablename__ = "elimination_results"

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    pairing_id = Column(Integer, ForeignKey("pairings.id"), nullable=False)
    elimination_order = Column(Integer, nullable=False)

    season = relationship("Season", back_populates="eliminations")
    pairing = relationship("Pairing", back_populates="elimination_results")

    __table_args__ = (
        UniqueConstraint("season_id", "pairing_id", name="uq_elimination_pairing"),
    )
