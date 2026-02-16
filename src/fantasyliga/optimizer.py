from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pulp


@dataclass
class Formation:
    gk: int
    df: int
    mf: int
    fw: int

    @property
    def size(self) -> int:
        return self.gk + self.df + self.mf + self.fw


def parse_formation(raw: str) -> Formation:
    parts = [int(x) for x in raw.split("-")]
    if len(parts) != 4:
        raise ValueError("Formace musí být ve formátu např. 1-4-4-2")
    return Formation(parts[0], parts[1], parts[2], parts[3])


def _norm_pos(pos: str) -> str:
    p = (pos or "").lower()
    if "brank" in p:
        return "GK"
    if "obr" in p:
        return "DF"
    if "zálož" in p or "zaloz" in p:
        return "MF"
    if "út" in p or "ut" in p:
        return "FW"
    return "UNK"


def optimize_lineup(
    input_csv: Path,
    output_csv: Path,
    *,
    budget: float,
    formation: Formation,
    max_from_team: int,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    df = df.copy()
    df["pos"] = df["position"].fillna("").map(_norm_pos)
    df = df[df["pos"].isin(["GK", "DF", "MF", "FW"])]

    problem = pulp.LpProblem("best_lineup", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in df.index}

    problem += pulp.lpSum(df.loc[i, "expected_points"] * x[i] for i in df.index)

    problem += pulp.lpSum(df.loc[i, "price_m"] * x[i] for i in df.index) <= budget
    problem += pulp.lpSum(x[i] for i in df.index) == formation.size

    problem += pulp.lpSum(x[i] for i in df.index if df.loc[i, "pos"] == "GK") == formation.gk
    problem += pulp.lpSum(x[i] for i in df.index if df.loc[i, "pos"] == "DF") == formation.df
    problem += pulp.lpSum(x[i] for i in df.index if df.loc[i, "pos"] == "MF") == formation.mf
    problem += pulp.lpSum(x[i] for i in df.index if df.loc[i, "pos"] == "FW") == formation.fw

    for team, sdf in df.groupby("team"):
        idxs = list(sdf.index)
        problem += pulp.lpSum(x[i] for i in idxs) <= max_from_team

    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Optimalizace nenašla optimální řešení. Status={pulp.LpStatus[status]}")

    chosen = df[[pulp.value(x[i]) > 0.5 for i in df.index]].copy()
    chosen = chosen.sort_values(["pos", "expected_points"], ascending=[True, False])
    chosen.to_csv(output_csv, index=False)
    return chosen
