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
ONLINE_TRIGGER = "be able to log back"

GAME_EMOJIS = {
    "destiny": ":destlogo:",
    "marathon": ":marathon:",
}

GAME_LABELS = {
    "destiny": "Destiny 2",
    "marathon": "Marathon",
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
    :emoji: __**Maintenance Nom**__ du <t:UNIX:D>:
    - :pencil:: Update X.X.X
    :x: Arrêt serv <t:UNIX:t> | :white_check_mark: Retour serv <t:UNIX:t> | :repeat: Débute: __**<t:UNIX:R>**__

    Retourne None si aucun événement ne matche.
    """
    messages: list[str] = []

    for event in data.get("events", []):
        steps = event.get("steps", [])

        # Cherche le step offline
        offline_step = None
        for step in steps:
            for detail in step.get("details", []):
                if OFFLINE_TRIGGER in detail.lower():
                    offline_step = step
                    break
            if offline_step is not None:
                break

        if offline_step is None or not offline_step.get("time_utc"):
            continue

        # Cherche le step online (retour serveurs)
        online_step = None
        for step in steps:
            for detail in step.get("details", []):
                if ONLINE_TRIGGER in detail.lower():
                    online_step = step
                    break
            if online_step is not None:
                break

        off_unix = _iso_to_unix(offline_step["time_utc"])

        game_emoji = GAME_EMOJIS.get(data["game"], "🎮")
        game_label = GAME_LABELS.get(data["game"], data["game"].title())

        lines: list[str] = []
        lines.append(f"{game_emoji} __**Maintenance {game_label}**__ du <t:{off_unix}:D>:")
        lines.append(f"- :pencil:: {event['event_type']}")

        ret_part = ""
        if online_step and online_step.get("time_utc"):
            ret_unix = _iso_to_unix(online_step["time_utc"])
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