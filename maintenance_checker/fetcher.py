"""
fetcher.py — Récupère les articles Server Status depuis l'API Zendesk.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp
import asyncio

from .models import Game

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


async def fetch_article_body(game: Game) -> Optional[str]:
    """
    Récupère le body HTML d'un article Zendesk Help Center.

    Returns:
        Le body HTML (str) ou None en cas d'erreur.
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
                article = data.get("article")
                if article:
                    return article.get("body")
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error("Erreur réseau pour %s : %s", game.value, e)
        return None