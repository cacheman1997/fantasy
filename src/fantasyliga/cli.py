from __future__ import annotations

import argparse
from pathlib import Path

from .optimizer import optimize_lineup, parse_formation
from .scraper import scrape_my_team_data
from .transform import build_player_table


def cmd_scrape(args: argparse.Namespace) -> None:
    out = scrape_my_team_data(
        Path(args.out_dir),
        headful=args.headful,
        auto_login=args.auto_login,
        max_players=args.max_players,
    )
    print("[OK] Data stažena:", out)


def cmd_build(args: argparse.Namespace) -> None:
    out = build_player_table(Path(args.data_dir))
    print(f"[OK] Vytvořeno: {out}")


def cmd_optimize(args: argparse.Namespace) -> None:
    formation = parse_formation(args.formation)
    chosen = optimize_lineup(
        Path(args.input),
        Path(args.output),
        budget=args.budget,
        formation=formation,
        max_from_team=args.max_from_team,
    )
    print("[OK] Nejlepší sestava: ")
    print(chosen[["player_name", "team", "position", "price_m", "expected_points"]])
    print("\nSoučet ceny:", round(chosen["price_m"].sum(), 2))
    print("Součet expected_points:", round(chosen["expected_points"].sum(), 2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FantasyLiga extractor + lineup optimizer")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("scrape")
    s.add_argument("--out-dir", default="data")
    s.add_argument("--headful", action="store_true")
    s.add_argument("--auto-login", action="store_true")
    s.add_argument("--max-players", type=int, default=20)
    s.set_defaults(func=cmd_scrape)

    b = sub.add_parser("build-player-table")
    b.add_argument("--data-dir", default="data")
    b.set_defaults(func=cmd_build)

    o = sub.add_parser("optimize")
    o.add_argument("--input", default="data/players_table.csv")
    o.add_argument("--output", default="data/best_lineup.csv")
    o.add_argument("--budget", type=float, default=100.0)
    o.add_argument("--formation", default="1-4-4-2")
    o.add_argument("--max-from-team", type=int, default=3)
    o.set_defaults(func=cmd_optimize)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
