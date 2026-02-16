from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _extract_recent_points(recent_matches: list[dict]) -> list[float]:
    out = []
    for m in recent_matches or []:
        raw = (m or {}).get("detail_raw", "")
        lines = [x.strip() for x in raw.split("\n") if x.strip()]
        for i, line in enumerate(lines):
            if line.lower().startswith("celkem bodů") and i + 1 < len(lines):
                try:
                    out.append(float(lines[i + 1].replace(",", ".")))
                except ValueError:
                    pass
    return out


def build_player_table(data_dir: Path) -> Path:
    latest = json.loads((data_dir / "latest.json").read_text(encoding="utf-8"))
    players_path = Path(latest["players"])
    players = json.loads(players_path.read_text(encoding="utf-8"))

    rows = []
    for p in players:
        recent_pts = _extract_recent_points(p.get("recent_matches") or [])
        last_5 = recent_pts[:5]
        avg_last_5 = sum(last_5) / len(last_5) if last_5 else 0.0

        total_points = float(p.get("total_points") or 0.0)
        matches_played = float((p.get("stats") or {}).get("Zápasy") or 0.0)
        long_term_ppg = (total_points / matches_played) if matches_played > 0 else 0.0

        expected_points = 0.7 * long_term_ppg + 0.3 * avg_last_5

        rows.append(
            {
                "player_name": p.get("player_name"),
                "team": p.get("team"),
                "position": p.get("position"),
                "age": p.get("age"),
                "price_m": float(p.get("price_m") or 0.0),
                "total_points": total_points,
                "ownership_pct": float(p.get("ownership_pct") or 0.0),
                "matches_played": matches_played,
                "avg_points_last_5": round(avg_last_5, 3),
                "expected_points": round(expected_points, 3),
            }
        )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["player_name"]).drop_duplicates(subset=["player_name"], keep="first")

    out = data_dir / "players_table.csv"
    df.to_csv(out, index=False)
    return out
