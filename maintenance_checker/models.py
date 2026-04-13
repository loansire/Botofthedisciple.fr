"""
models.py — Modèles de données pour les maintenances Bungie.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Game(Enum):
    DESTINY = "destiny"
    MARATHON = "marathon"


# Mapping nom string → enum (pour l'API publique)
_GAME_ALIASES: dict[str, Game] = {
    "destiny": Game.DESTINY,
    "destiny2": Game.DESTINY,
    "destiny 2": Game.DESTINY,
    "d2": Game.DESTINY,
    "marathon": Game.MARATHON,
}


def resolve_game(name: str) -> Game:
    """
    Résout un nom de jeu (string) en enum Game.
    Accepte : 'destiny', 'destiny2', 'd2', 'marathon' (insensible à la casse).

    Raises:
        ValueError: si le nom n'est pas reconnu.
    """
    key = name.strip().lower()
    if key not in _GAME_ALIASES:
        valid = ", ".join(sorted(_GAME_ALIASES.keys()))
        raise ValueError(f"Jeu inconnu : '{name}'. Valeurs acceptées : {valid}")
    return _GAME_ALIASES[key]


@dataclass
class MaintenanceStep:
    """Un créneau horaire dans un planning de maintenance."""
    time_primary: str       # ex: "5:00 AM PDT"
    time_secondary: str     # ex: "UTC-7" ou "5 PM UTC"
    details: list[str]      # liste des bullet points
    time_utc: Optional[str] = None   # ISO 8601, ex: "2026-04-07T12:00:00Z"
    approximate: bool = False        # True si le texte contenait "~"

    def to_dict(self) -> dict:
        d = {
            "time_primary": self.time_primary,
            "time_secondary": self.time_secondary,
            "details": self.details,
        }
        if self.time_utc:
            d["time_utc"] = self.time_utc
        if self.approximate:
            d["approximate"] = True
        return d


@dataclass
class MaintenanceEvent:
    """Un événement de maintenance (date + type + créneaux)."""
    game: Game
    title: str              # ex: "Tuesday, April 7 2026 — Update 1.0.5.3"
    date_raw: str           # la date brute extraite
    event_type: str         # ex: "Update 1.0.5.3", "Background Maintenance"
    steps: list[MaintenanceStep] = field(default_factory=list)
    start_time_utc: Optional[str] = None
    end_time_utc: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "game": self.game.value,
            "title": self.title,
            "date_raw": self.date_raw,
            "event_type": self.event_type,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.start_time_utc:
            d["start_time_utc"] = self.start_time_utc
        if self.end_time_utc:
            d["end_time_utc"] = self.end_time_utc
        return d