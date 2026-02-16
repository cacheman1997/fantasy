# FantasyLiga Data Extractor & Best Lineup Optimizer

Tento mini-projekt řeší přesně váš use-case:

1. **Přihlášení do https://fantasyliga.cz/my-team** (interaktivně nebo přes ENV).
2. **Stažení dat hráčů + statistik zápasů** do JSON/CSV.
3. **Výpočet nejlepší sestavy** podle očekávaných bodů s omezeními (rozpočet, formace, limity na klub).

> ⚠️ Používejte pouze na vlastním účtu a podle podmínek služby.

---

## Instalace

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

## 1) Sběr dat z webu (po přihlášení)

### Varianta A: manuální login (doporučeno)

```bash
python -m fantasyliga.cli scrape --headful
```

Skript otevře browser, nechá vás se přihlásit a pak:
- nasbírá JSON odpovědi z XHR/fetch,
- projde hráče v pravém seznamu,
- otevře detail hráče,
- projde dostupné řádky "Odehrané zápasy",
- uloží surová i normalizovaná data do `data/`.

### Varianta B: login přes ENV

```bash
export FANTASY_EMAIL="vas@email.cz"
export FANTASY_PASSWORD="tajneheslo"
python -m fantasyliga.cli scrape --headful --auto-login
```

---

## 2) Vygenerování modelovací tabulky hráčů

```bash
python -m fantasyliga.cli build-player-table
```

Výstup: `data/players_table.csv`

Tabulka obsahuje např.:
- `player_name`
- `team`
- `position`
- `price_m`
- `total_points`
- `ownership_pct`
- `matches_played`
- `avg_points_last_5`
- `expected_points`

`expected_points` je aktuálně jednoduchý baseline (vážený mix dlouhodobých bodů a formy z posledních zápasů), který lze snadno upravit.

---

## 3) Návrh nejlepší sestavy

```bash
python -m fantasyliga.cli optimize \
  --input data/players_table.csv \
  --budget 100 \
  --formation "1-4-4-2" \
  --max-from-team 3
```

Výstup:
- `data/best_lineup.csv`
- souhrn v konzoli (cena, očekávané body, složení)

---

## Jak to rozšířit do „statistického software“

- Přidejte pravidelný ETL (cron/GitHub Actions) pro aktualizaci dat po každém kole.
- Rozšiřte predikci `expected_points` (např. XG, síla soupeře doma/venku, penalizace za karetní riziko).
- Přidejte web UI (Streamlit/FastAPI + React) s:
  - simulací více formací,
  - citlivostní analýzou (co když hráč nenastoupí),
  - doporučením přestupů podle budgetu.

---

## Struktura projektu

- `src/fantasyliga/scraper.py` – sběr dat z webu pomocí Playwright
- `src/fantasyliga/transform.py` – normalizace dat do tabulky hráčů
- `src/fantasyliga/optimizer.py` – optimalizace sestavy (MILP přes PuLP)
- `src/fantasyliga/cli.py` – CLI příkazy

