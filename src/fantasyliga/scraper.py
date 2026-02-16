from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


@dataclass
class PlayerSnapshot:
    player_name: str | None
    team: str | None
    position: str | None
    age: int | None
    total_points: float | None
    price_m: float | None
    ownership_pct: float | None
    stats: dict[str, Any]
    recent_matches: list[dict[str, Any]]


_NUMBER_RE = re.compile(r"-?\d+(?:[\.,]\d+)?")


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None
    m = _NUMBER_RE.search(value)
    if not m:
        return None
    return float(m.group(0).replace(",", "."))


def _safe_text(page: Page, selector: str) -> str | None:
    locator = page.locator(selector)
    if locator.count() == 0:
        return None
    txt = locator.first.inner_text().strip()
    return txt or None


def _collect_stats_block(page: Page) -> dict[str, Any]:
    # Cíl: blok "Statistiky" v panelu hráče
    stats: dict[str, Any] = {}
    rows = page.locator("text=Statistiky").locator("xpath=../../..//div")
    count = min(rows.count(), 300)
    # fallback: vezmeme viditelné texty a zkusíme je párovat po dvojicích
    lines = []
    for i in range(count):
        t = rows.nth(i).inner_text().strip()
        if t:
            lines.extend([x.strip() for x in t.split("\n") if x.strip()])

    # Heuristika: label, value
    for i in range(len(lines) - 1):
        if _parse_number(lines[i + 1]) is not None and _parse_number(lines[i]) is None:
            stats[lines[i]] = _parse_number(lines[i + 1])

    return stats


def _collect_match_rows(page: Page, max_rows: int = 10) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    # "Odehrané zápasy" sekce v detailu hráče
    rows = page.locator("text=Odehrané zápasy").locator("xpath=../../..//div[contains(@class, 'cursor') or contains(@class,'match') or .//text()]")
    total = min(rows.count(), max_rows)

    for i in range(total):
        row = rows.nth(i)
        text = row.inner_text().strip()
        if not text or "kolo" not in text.lower():
            continue
        try:
            row.click(timeout=1200)
            page.wait_for_timeout(300)
        except Exception:
            pass

        detail_lines = page.locator("text=Statistiky zápasu").locator("xpath=../../..//div").all_inner_texts()
        flat = "\n".join(x.strip() for x in detail_lines if x.strip())

        matches.append(
            {
                "match_row_text": text,
                "detail_raw": flat,
            }
        )

    return matches


def _snapshot_player(page: Page) -> PlayerSnapshot:
    header = _safe_text(page, "text=Detail hráče")
    if not header:
        raise RuntimeError("Detail hráče nebyl nalezen. Ujistěte se, že je otevřen pravý panel hráče.")

    badge_texts = page.locator("text=Detail hráče").locator("xpath=../..//button | ../..//div").all_inner_texts()
    badge_blob = " \n ".join(x.strip() for x in badge_texts if x.strip())

    points = _parse_number(badge_blob)
    price = None
    ownership = None
    for token in badge_blob.split():
        if "M" in token.upper() and price is None:
            price = _parse_number(token)
        if "%" in token and ownership is None:
            ownership = _parse_number(token)

    name_line = _safe_text(page, "text=Detail hráče >> xpath=../../..//div[contains(@class,'font')][2]")
    sub_line = _safe_text(page, "text=Detail hráče >> xpath=../../..//div[contains(text(),' - ')]")

    team = None
    position = None
    age = None
    if sub_line:
        # očekávaný formát: "Slavia - Záložník - 30 let"
        parts = [p.strip() for p in sub_line.split("-")]
        if len(parts) >= 1:
            team = parts[0]
        if len(parts) >= 2:
            position = parts[1]
        if len(parts) >= 3:
            age = int(_parse_number(parts[2]) or 0) or None

    stats = _collect_stats_block(page)
    recent_matches = _collect_match_rows(page)

    return PlayerSnapshot(
        player_name=name_line,
        team=team,
        position=position,
        age=age,
        total_points=points,
        price_m=price,
        ownership_pct=ownership,
        stats=stats,
        recent_matches=recent_matches,
    )


def scrape_my_team_data(
    out_dir: Path,
    *,
    headful: bool = True,
    auto_login: bool = False,
    max_players: int = 20,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    captured_api: list[dict[str, Any]] = []
    players: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context()
        page = context.new_page()

        def on_response(resp):
            try:
                ctype = (resp.headers or {}).get("content-type", "")
                if "application/json" not in ctype:
                    return
                url = resp.url
                if "fantasy" not in url:
                    return
                body = resp.json()
                captured_api.append({"url": url, "status": resp.status, "json": body})
            except Exception:
                return

        page.on("response", on_response)

        page.goto("https://fantasyliga.cz/my-team", wait_until="domcontentloaded")

        if auto_login:
            email = os.getenv("FANTASY_EMAIL")
            password = os.getenv("FANTASY_PASSWORD")
            if not email or not password:
                raise RuntimeError("Pro --auto-login je nutné nastavit FANTASY_EMAIL a FANTASY_PASSWORD.")

            page.fill("input[type='email']", email)
            page.fill("input[type='password']", password)
            page.locator("button:has-text('Přihlásit')").click()

        # čekání na ruční přihlášení a načtení týmové stránky
        print("[INFO] Přihlaste se a otevřete stránku 'Můj tým'. Čekám max 180 s...")
        page.wait_for_timeout(4000)
        for _ in range(180):
            if page.locator("text=Můj tým").count() > 0 and page.locator("text=Seznam hráčů").count() > 0:
                break
            page.wait_for_timeout(1000)
        else:
            raise RuntimeError("Nepodařilo se detekovat načtenou stránku 'Můj tým'.")

        # klikání do seznamu hráčů vpravo
        player_rows = page.locator("text=Seznam hráčů").locator("xpath=../../..//div[contains(@class,'cursor') or contains(@class,'player')]")
        count = min(player_rows.count(), max_players)

        for i in range(count):
            row = player_rows.nth(i)
            try:
                row.click(timeout=1500)
                page.wait_for_timeout(500)
                snap = _snapshot_player(page)
                players.append(asdict(snap))
            except Exception:
                continue

        browser.close()

    ts = int(time.time())
    raw_api_file = out_dir / f"raw_api_{ts}.json"
    players_file = out_dir / f"players_{ts}.json"

    raw_api_file.write_text(json.dumps(captured_api, ensure_ascii=False, indent=2), encoding="utf-8")
    players_file.write_text(json.dumps(players, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_ptr = {
        "raw_api": str(raw_api_file),
        "players": str(players_file),
        "created_at_unix": ts,
    }
    (out_dir / "latest.json").write_text(json.dumps(latest_ptr, ensure_ascii=False, indent=2), encoding="utf-8")

    return latest_ptr
