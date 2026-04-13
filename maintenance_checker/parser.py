"""
parser.py — Parse le HTML des articles Zendesk Server Status en MaintenanceEvent.

Reprend la logique de parsing de server_status_monitor.py, isolée en module.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .models import Game, MaintenanceEvent, MaintenanceStep


# ──────────────────────────────────────────────
# Parsing temporel
# ──────────────────────────────────────────────

_TZ_OFFSETS: dict[str, int] = {
    "PDT": -7, "PST": -8, "PACIFIC": -7,
    "MDT": -6, "MST": -7,
    "CDT": -5, "CST": -6,
    "EDT": -4, "EST": -5,
    "UTC": 0, "GMT": 0,
    "BST": 1, "CET": 1, "CEST": 2,
}

_TIME_RE = re.compile(
    r"~?\s*"
    r"(\d{1,2})"
    r"(?::(\d{2}))?"
    r"\s*(AM|PM)"
    r"\s+([A-Za-z\-]+)",
    re.IGNORECASE,
)

_OFFSET_RE = re.compile(
    r"[(\s]*"
    r"(?:UTC\s*([+-]?\d{1,2})|([+-]?\d{1,2})\s*UTC)"
    r"[)\s]*",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r",?\s+"
    r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date_from_title(date_raw: str) -> Optional[datetime]:
    """Parse 'Tuesday, April 7 2026' → datetime(2026, 4, 7)."""
    m = _DATE_RE.search(date_raw)
    if not m:
        return None
    month_str, day_str, year_str = m.group(1), m.group(2), m.group(3)
    month = _MONTHS.get(month_str.lower())
    if not month:
        return None
    try:
        return datetime(int(year_str), month, int(day_str))
    except ValueError:
        return None


def _resolve_tz_offset(tz_str: str, secondary: str = "") -> Optional[int]:
    """Résout un offset UTC en heures à partir du texte timezone."""
    key = tz_str.strip().upper().rstrip(".,")
    if key in _TZ_OFFSETS:
        return _TZ_OFFSETS[key]

    for text in (tz_str, secondary):
        m = _OFFSET_RE.search(text)
        if m:
            offset_str = m.group(1) or m.group(2)
            try:
                return int(offset_str)
            except ValueError:
                pass

    return None


def _parse_step_time(
    time_primary: str,
    time_secondary: str,
    base_date: Optional[datetime],
) -> tuple[Optional[str], bool]:
    """Parse le texte horaire d'un step → (iso_utc, approximate)."""
    if not base_date:
        return None, False

    approximate = "~" in time_primary

    m = _TIME_RE.search(time_primary)
    if not m:
        return None, approximate

    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3).upper()
    tz_str = m.group(4)

    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    offset = _resolve_tz_offset(tz_str, time_secondary)
    if offset is None:
        # Fallback : essaie de parser le secondaire comme un time UTC direct
        m2 = _TIME_RE.search(time_secondary)
        if m2:
            h2 = int(m2.group(1))
            min2 = int(m2.group(2)) if m2.group(2) else 0
            ampm2 = m2.group(3).upper()
            tz2 = m2.group(4)
            if ampm2 == "PM" and h2 != 12:
                h2 += 12
            elif ampm2 == "AM" and h2 == 12:
                h2 = 0
            off2 = _resolve_tz_offset(tz2, "")
            if off2 is not None:
                dt_utc = base_date.replace(
                    hour=h2, minute=min2, second=0, microsecond=0,
                    tzinfo=timezone(timedelta(hours=off2)),
                ).astimezone(timezone.utc)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), approximate
        return None, approximate

    local_tz = timezone(timedelta(hours=offset))
    dt_local = base_date.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
        tzinfo=local_tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)

    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), approximate


def _enrich_steps_with_utc(
    steps: list[MaintenanceStep],
    date_raw: str,
) -> None:
    """Ajoute time_utc et approximate à chaque step in-place."""
    base_date = _parse_date_from_title(date_raw)
    for step in steps:
        utc_str, approx = _parse_step_time(
            step.time_primary, step.time_secondary, base_date,
        )
        step.time_utc = utc_str
        step.approximate = approx


def _set_event_bounds(event: MaintenanceEvent) -> None:
    """Définit start_time_utc / end_time_utc depuis les steps."""
    utc_times = [s.time_utc for s in event.steps if s.time_utc]
    if utc_times:
        event.start_time_utc = utc_times[0]
        event.end_time_utc = utc_times[-1]


# ──────────────────────────────────────────────
# Parser HTML → MaintenanceEvent
# ──────────────────────────────────────────────

def _clean_text(el: Tag | str) -> str:
    """Extrait et nettoie le texte d'un élément BS4."""
    text = el.get_text(separator=" ", strip=True) if isinstance(el, Tag) else str(el)
    return re.sub(r"\s+", " ", text).strip()


def _parse_table(table: Tag) -> list[MaintenanceStep]:
    """Parse un <table> de maintenance en liste de MaintenanceStep."""
    steps = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        time_primary = _clean_text(cells[0])
        time_secondary = _clean_text(cells[1])
        details = [_clean_text(li) for li in cells[2].find_all("li") if _clean_text(li)]

        if time_primary or details:
            steps.append(MaintenanceStep(
                time_primary=time_primary,
                time_secondary=time_secondary,
                details=details,
            ))
    return steps


_TITLE_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r",?\s+"
    r"[\w\s,]+\d{4}"
    r"\s*[—–\-]\s*"
    r".+",
    re.IGNORECASE,
)


def _extract_title(text: str) -> Optional[str]:
    """Retourne le titre de maintenance si le texte matche le pattern."""
    text = text.strip()
    if _TITLE_RE.match(text):
        return text
    return None


def _split_title(title: str) -> tuple[str, str]:
    """Sépare 'Date — Type' en (date_raw, event_type)."""
    for sep in ("—", "–", "-"):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return title, "Unknown"


def parse_maintenance_events(html_body: str, game: Game) -> list[MaintenanceEvent]:
    """
    Parse le body HTML d'un article server status et retourne
    la liste des MaintenanceEvent trouvés.
    """
    soup = BeautifulSoup(html_body, "html.parser")
    events: list[MaintenanceEvent] = []

    landmarks: list[tuple[str, str | Tag]] = []
    seen_titles: set[str] = set()
    seen_table_ids: set[int] = set()

    for el in soup.descendants:
        if not isinstance(el, Tag):
            continue

        if el.name in ("span", "div", "p", "strong"):
            if el.find_parent("table"):
                continue
            text = _clean_text(el)
            found = _extract_title(text)
            if found and found not in seen_titles and len(text) < 200:
                children_texts = {
                    _clean_text(c) for c in el.find_all(["span", "strong", "div", "p"])
                    if isinstance(c, Tag) and c != el
                }
                child_has_same = any(_extract_title(ct) == found for ct in children_texts)
                if not child_has_same:
                    seen_titles.add(found)
                    landmarks.append(("title", found))

        elif el.name == "table":
            tid = id(el)
            if tid not in seen_table_ids:
                seen_table_ids.add(tid)
                landmarks.append(("table", el))

    i = 0
    while i < len(landmarks):
        kind, value = landmarks[i]
        if kind == "title":
            title = str(value)
            date_raw, event_type = _split_title(title)

            steps = []
            if i + 1 < len(landmarks) and landmarks[i + 1][0] == "table":
                table_tag = landmarks[i + 1][1]
                assert isinstance(table_tag, Tag)
                steps = _parse_table(table_tag)
                i += 2
            else:
                i += 1

            events.append(MaintenanceEvent(
                game=game,
                title=title,
                date_raw=date_raw,
                event_type=event_type,
                steps=steps,
            ))

            _enrich_steps_with_utc(steps, date_raw)
            _set_event_bounds(events[-1])
        else:
            i += 1

    return events