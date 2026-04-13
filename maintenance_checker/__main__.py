"""
__main__.py — Point d'entrée CLI pour maintenance_checker.

Usage:
    python -m maintenance_checker                # les deux jeux
    python -m maintenance_checker destiny         # Destiny 2 seulement
    python -m maintenance_checker marathon        # Marathon seulement
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

try:
    from . import get_maintenances
    from .models import resolve_game
except ImportError:
    # Exécution directe (python __main__.py) : ajoute le parent au path
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from maintenance_checker import get_maintenances
    from maintenance_checker.models import resolve_game

ALL_GAMES = ["destiny", "marathon"]


async def run(games: list[str]) -> int:
    """Fetch et print le JSON pour chaque jeu. Retourne 0 si OK."""
    success = True

    for game in games:
        data = await get_maintenances(game)
        if data is None:
            print(f"❌ Échec pour {game}", file=sys.stderr)
            success = False
            continue

        print(json.dumps(data, indent=2, ensure_ascii=False))

        # Séparateur visuel entre les jeux si plusieurs
        if len(games) > 1 and game != games[-1]:
            print()

    return 0 if success else 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Argument optionnel : nom du jeu
    if len(sys.argv) > 1:
        game_arg = sys.argv[1].lower()
        # Validation rapide
        try:
            resolve_game(game_arg)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
        games = [game_arg]
    else:
        games = ALL_GAMES

    exit_code = asyncio.run(run(games))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()