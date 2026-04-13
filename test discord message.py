"""
test_discord_format.py — Fetch les maintenances live et génère
un texte formaté Discord prêt à copier-coller.

Filtre : ne garde que l'événement contenant "brought offline for expected maintenance"
et affiche le message formaté avec timestamps Discord.

Usage:
    python test_discord_format.py                # les deux jeux
    python test_discord_format.py destiny
    python test_discord_format.py marathon
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from maintenance_checker import get_maintenances


# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

OFFLINE_TRIGGER = "brought offline for expected maintenance"

GAME_NAMES = {
    "destiny": "Destiny 2",
    "marathon": "Marathon",
}

_MOIS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _iso_to_unix(iso_str: str) -> int:
    """Convertit '2026-04-07T12:30:00Z' en timestamp Unix."""
    dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# ──────────────────────────────────────────────
# Formatage Discord
# ──────────────────────────────────────────────

def format_discord_message(data: dict) -> str | None:
    """
    Formate un message Discord pour un jeu.

    Format :
    __**Maintenance**__ et mise à jour aujourd'hui:
    - :pencil:: ❖ Update X.X.X
    :x: Arrêt serv <t:UNIX:t> | :white_check_mark: Retour serv <t:UNIX:t> | :repeat: Débute: __**<t:UNIX:R>**__

    Retourne None si aucun événement ne matche.
    """
    messages: list[str] = []

    for event in data.get("events", []):
        steps = event.get("steps", [])

        # Cherche le step avec le trigger
        offline_idx = None
        for i, step in enumerate(steps):
            for detail in step.get("details", []):
                if OFFLINE_TRIGGER in detail.lower():
                    offline_idx = i
                    break
            if offline_idx is not None:
                break

        if offline_idx is None:
            continue

        offline_step = steps[offline_idx]
        return_step = steps[offline_idx + 1] if offline_idx + 1 < len(steps) else None

        if not offline_step.get("time_utc"):
            continue

        off_unix = _iso_to_unix(offline_step["time_utc"])

        # Date en français depuis le timestamp UTC
        dt = datetime.strptime(offline_step["time_utc"], "%Y-%m-%dT%H:%M:%SZ")
        date_fr = f"{dt.day} {_MOIS_FR[dt.month]} {dt.year}"
        game_name = GAME_NAMES.get(data["game"], data["game"].title())

        lines: list[str] = []
        lines.append(f"__**Maintenance {game_name}**__ et mise à jour du {date_fr}:")
        lines.append(f"- :pencil:: ❖ {event['event_type']}")

        ret_part = ""
        if return_step and return_step.get("time_utc"):
            ret_unix = _iso_to_unix(return_step["time_utc"])
            ret_part = f" | :white_check_mark: Retour serv <t:{ret_unix}:t>"

        lines.append(
            f":x: Arrêt serv <t:{off_unix}:t>"
            f"{ret_part}"
            f" | :repeat: Débute: __**<t:{off_unix}:R>**__"
        )

        messages.append("\n".join(lines))

    if not messages:
        return None

    return "\n\n".join(messages)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def run(games: list[str]) -> None:
    for game in games:
        print(f"\n{'='*50}")
        print(f" DISCORD MESSAGE — {game.upper()}")
        print(f"{'='*50}\n")

        data = await get_maintenances(game)
        if data is None:
            print(f"❌ Impossible de récupérer les données pour {game}")
            continue

        message = format_discord_message(data)
        if message is None:
            print(f"ℹ️  Aucune maintenance avec mise hors ligne trouvée pour {game}")
            continue

        print(message)
        print(f"\n{'─'*50}")
        print(f"📏 {len(message)} caractères")


def main() -> None:
    if len(sys.argv) > 1:
        games = [sys.argv[1].lower()]
    else:
        games = ["destiny", "marathon"]

    asyncio.run(run(games))


if __name__ == "__main__":
    main()