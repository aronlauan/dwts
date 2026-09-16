from typing import List, Optional

from pydantic import BaseModel, Field


class PairingCreate(BaseModel):
    star_name: str
    pro_name: str


class SeasonCreate(BaseModel):
    name: Optional[str] = "DWTS 2026"


class PickSubmission(BaseModel):
    name: str
    season_id: int
    predictions: List[str] = Field(..., min_length=1)


class EliminationCreate(BaseModel):
    season_id: Optional[int] = None
    star_name: str


class UserCreate(BaseModel):
    username: str


class SiteMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)


class HighlightYoutubeCreate(BaseModel):
    youtube_url: str = Field(..., min_length=1)


class AdminLogin(BaseModel):
    username: str
    password: str
