"""
fetcher.py — Récupère les articles Server Status depuis l'API Zendesk.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp
import asyncio

# Import compatible avec :
#   - import via package (from maintenance_checker.fetcher import ...)
#   - exécution directe du fichier (Run dans PyCharm sur fetcher.py)
try:
    from .models import Game
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from maintenance_checker.models import Game

logger = logging.getLogger(__name__)

# Configuration des articles Zendesk par jeu
ARTICLES = {
    Game.DESTINY: {
        "base_url": "https://help.bungie.net",
        "article_id": 360049199271,
        "locale": "en-us",
    },
    Game.MARATHON: {
        "base_url": "https://help.marathonthegame.com",
        "article_id": 39001626488596,
        "locale": "en-us",
    },
}


async def _fetch_article_raw(game: Game) -> Optional[dict]:
    """
    Récupère l'objet article complet depuis l'API Zendesk Help Center.

    Returns:
        Le dict 'article' brut renvoyé par l'API (clés : id, title, body,
        created_at, updated_at, edited_at, etc.) ou None en cas d'erreur.
    """
    cfg = ARTICLES[game]
    url = (
        f"{cfg['base_url']}/api/v2/help_center"
        f"/{cfg['locale']}/articles/{cfg['article_id']}.json"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(
                        "Erreur HTTP %d pour %s (%s)", resp.status, game.value, url,
                    )
                    return None
                data = await resp.json()
                return data.get("article")
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error("Erreur réseau pour %s : %s", game.value, e)
        return None


async def fetch_article_body(game: Game) -> tuple[Optional[str], Optional[str]]:
    """
    Récupère le body HTML d'un article Zendesk Help Center,
    ainsi que sa date de dernière mise à jour.

    Returns:
        Un tuple (body_html, updated_at_iso).
        Les deux valeurs sont None en cas d'erreur réseau / HTTP.
        updated_at peut être None si le champ est absent de la réponse,
        même si le body a été récupéré avec succès.
    """
    article = await _fetch_article_raw(game)
    if article is None:
        return None, None
    return article.get("body"), article.get("updated_at")


# ──────────────────────────────────────────────
# Test standalone : python fetcher.py [destiny|marathon]
# ──────────────────────────────────────────────

async def _main(games: list[str]) -> int:
    """
    Fetch et affiche le JSON complet de chaque article (sans le body HTML),
    pour debug / inspection des champs Zendesk disponibles.
    """
    import json
    try:
        from .models import resolve_game
    except ImportError:
        from maintenance_checker.models import resolve_game

    success = True
    for game_name in games:
        game_enum = resolve_game(game_name)
        article = await _fetch_article_raw(game_enum)

        if article is None:
            print(f"❌ Échec fetch pour {game_name}")
            success = False
            continue

        # Remplace le body par un placeholder pour ne pas spammer la console
        body_len = len(article.get("body") or "")
        article_lite = {**article, "body": f"<HTML body omitted: {body_len} chars>"}

        print(f"=== {game_name} ===")
        print(json.dumps(article_lite, indent=2, ensure_ascii=False))
        print()

    return 0 if success else 1


def main() -> None:
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) > 1:
        games = [sys.argv[1].lower()]
    else:
        games = ["destiny", "marathon"]

    sys.exit(asyncio.run(_main(games)))


if __name__ == "__main__":
    main()