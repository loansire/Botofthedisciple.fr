"""
maintenance_checker — Module de récupération des maintenances Bungie.

Usage comme module:
    from maintenance_checker import get_maintenances

    # Async
    data = await get_maintenances("destiny")
    data = await get_maintenances("marathon")

Usage standalone:
    python -m maintenance_checker
    python -m maintenance_checker destiny
    python -m maintenance_checker marathon
"""

from __future__ import annotations

import logging
from typing import Optional

from .models import Game, MaintenanceEvent, resolve_game
from .fetcher import fetch_article_body
from .parser import parse_maintenance_events

logger = logging.getLogger(__name__)


async def get_maintenances(game: str) -> Optional[dict]:
    """
    Récupère les maintenances programmées pour un jeu Bungie.

    Args:
        game: Nom du jeu. Accepte : 'destiny', 'destiny2', 'd2', 'marathon'
              (insensible à la casse).

    Returns:
        Un dict prêt à json.dumps() :
        {
            "game": "destiny",
            "events_count": 2,
            "events": [ ... ]
        }
        Retourne None si le fetch échoue.

    Raises:
        ValueError: si le nom du jeu n'est pas reconnu.
    """
    game_enum = resolve_game(game)

    body = await fetch_article_body(game_enum)
    if body is None:
        logger.error("Impossible de récupérer l'article pour %s", game_enum.value)
        return None

    events = parse_maintenance_events(body, game_enum)

    return {
        "game": game_enum.value,
        "events_count": len(events),
        "events": [e.to_dict() for e in events],
    }