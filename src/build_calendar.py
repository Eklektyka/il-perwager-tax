"""
Build a monthly sports calendar table 2019-2026.

Columns:
  year, month,
  nfl_games, nba_games, mlb_games, nhl_games, ncaab_games, ncaaf_games,
  nfl_playoff, nba_playoff, mlb_playoff, nhl_playoff, ncaab_postseason, ncaaf_postseason,
  super_bowl, march_madness, world_series,
  bears_postseason, bulls_postseason, cubs_postseason, whitesox_postseason, blackhawks_postseason

Game counts are league-wide totals (not per-team).
Playoff indicators are 1 if any playoff/postseason games occurred that month.
Chicago team postseason = 1 if that team played a postseason game that month.

Sources:
  - NFL: 272 reg-season games (2019-2020), 272 (2021 expanded to 17 games = 272 total),
    285 games (2022+, 17 games x 32 teams / 2 + extra). Actually:
    Pre-2021: 256 games (16 games x 32 teams / 2). 2021+: 272 games (17 games x 32 teams / 2).
    Playoffs: 11 games (2019), 13 games (2020, added extra wild card), 13 games (2021+).
  - NBA: ~1230 reg-season games (82 x 30 / 2). Playoffs: ~80-85 games.
  - MLB: ~2430 reg-season games (162 x 30 / 2). Playoffs: ~40-50 games.
  - NHL: ~1312 reg-season games (82 x 32 / 2; 31 teams before Seattle 2021-22).
    2019-20 COVID: shortened. 2020-21: 56-game season. Playoffs: ~80-85 games.
  - NCAA basketball: ~5,500+ games per season across D1.
  - NCAA football: ~800+ FBS games per season.

Monthly distributions are based on typical schedule patterns, adjusted for known
COVID disruptions (2019-20, 2020-21 seasons).

Idempotent: re-running overwrites the output.
"""

import pandas as pd
from pathlib import Path

CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


# ── NFL schedule by month ────────────────────────────────────────────────
# NFL regular season: Sep–Jan (some years have Week 1 in late Aug starting ~2023)
# Playoffs: Jan (Wild Card, Divisional, Conference), Feb (Super Bowl)
# Pre-2021: 256 reg games. 2021+: 272 reg games.
# Playoff games: 2019 season=11 (6WC+4Div+2CC+1SB)... actually:
#   Pre-2020 playoffs: 4 WC + 4 Div + 2 Conf + 1 SB = 11
#   2020+ playoffs: 6 WC + 4 Div + 2 Conf + 1 SB = 13

def nfl_season(season_year):
    """
    Return {(year,month): (reg_games, playoff_games, is_super_bowl)} for an NFL season.
    season_year is the fall year (e.g. 2024 for the 2024-25 season).
    """
    rows = {}
    if season_year <= 2020:
        total_reg = 256
    else:
        total_reg = 272

    if season_year <= 2019:
        total_playoff = 11
    else:
        total_playoff = 13

    # Typical monthly distribution of regular-season games
    # Sep: ~4 weeks (~64 games for 256 or ~64 for 272)
    # Oct: ~4-5 weeks
    # Nov: ~4 weeks
    # Dec: ~4-5 weeks
    # Jan: ~1 week (Week 17/18)

    if season_year == 2020:
        # COVID: season started on time but adjusted schedule
        # Sep: Weeks 1-3 (48 games)
        # Oct: Weeks 4-8 (77 games, some byes)
        # Nov: Weeks 9-12 (56 games)
        # Dec: Weeks 13-16 (60 games)
        # Jan: Week 17 + playoffs (15 + 6WC + 4Div = 25)
        # Feb: 2 Conf + 1 SB = 3
        rows[(2020, 9)] = (48, 0, False)
        rows[(2020, 10)] = (77, 0, False)
        rows[(2020, 11)] = (56, 0, False)
        rows[(2020, 12)] = (60, 0, False)
        rows[(2021, 1)] = (15, 10, False)
        rows[(2021, 2)] = (0, 3, True)
    elif season_year == 2019:
        rows[(2019, 9)] = (48, 0, False)
        rows[(2019, 10)] = (60, 0, False)
        rows[(2019, 11)] = (60, 0, False)
        rows[(2019, 12)] = (64, 0, False)
        rows[(2020, 1)] = (24, 8, False)
        rows[(2020, 2)] = (0, 3, True)
    else:
        # 2021+ (272 reg games, 13 playoff games)
        # Weeks 1-4 in Sep (~64 games), some seasons start late Aug
        has_aug = season_year >= 2023  # Thursday kickoff game in late Aug/early Sep

        if has_aug:
            # 1 game in late Aug (kickoff Thursday), rest in Sep
            aug_games = 1
            sep_games = 47  # ~3 weeks of full slates
        else:
            aug_games = 0
            sep_games = 48

        oct_games = 64  # ~4 full weeks
        nov_games = 60  # ~4 weeks (some byes)
        dec_games = 64  # ~4 weeks
        jan_reg = total_reg - aug_games - sep_games - oct_games - nov_games - dec_games

        if jan_reg < 0:
            # Adjust Dec down
            dec_games += jan_reg
            jan_reg = 0

        # Playoffs: Jan = WC(6) + Div(4), Feb = Conf(2) + SB(1)
        if has_aug and aug_games > 0:
            rows[(season_year, 8)] = (aug_games, 0, False)

        rows[(season_year, 9)] = (sep_games, 0, False)
        rows[(season_year, 10)] = (oct_games, 0, False)
        rows[(season_year, 11)] = (nov_games, 0, False)
        rows[(season_year, 12)] = (dec_games, 0, False)
        rows[(season_year + 1, 1)] = (jan_reg, 10, False)
        rows[(season_year + 1, 2)] = (0, 3, True)

    return rows


# ── NBA schedule by month ────────────────────────────────────────────────
# Regular season: ~1230 games (82 x 30 / 2). Oct–Apr.
# Playoffs: Apr–Jun. ~80 games.
# Play-in tournament: 2021+ (Apr, ~4-6 games)
# COVID 2019-20: suspended Mar 2020, resumed Jul-Oct 2020 in bubble.
# COVID 2020-21: started Dec 2020, 72-game season, ended May 2021. Playoffs May-Jul 2021.

def nba_season(season_year):
    """
    season_year is the start year (e.g. 2024 for 2024-25 season).
    Returns {(year,month): (reg_games, playoff_games)}.
    """
    rows = {}

    if season_year == 2019:
        # 2019-20: started Oct 2019, suspended Mar 11 2020, resumed Jul 30 2020
        # ~971 reg-season games played before suspension + ~88 in bubble
        rows[(2019, 10)] = (109, 0)
        rows[(2019, 11)] = (210, 0)
        rows[(2019, 12)] = (225, 0)
        rows[(2020, 1)] = (228, 0)
        rows[(2020, 2)] = (199, 0)
        # Suspended Mar 11
        rows[(2020, 3)] = (0, 0)  # ~3 days of games before suspension = ~20
        # Bubble: 8 seeding games per 22 teams = 88 games Jul 30 - Aug 14
        rows[(2020, 7)] = (2, 0)  # last 2 days of Jul
        rows[(2020, 8)] = (86, 16)  # rest of seeding + first round starts
        rows[(2020, 9)] = (0, 42)  # R1 continues, R2, conf semis
        rows[(2020, 10)] = (0, 23)  # conf finals + Finals
    elif season_year == 2020:
        # 2020-21: started Dec 22 2020, 72-game season
        rows[(2020, 12)] = (68, 0)
        rows[(2021, 1)] = (213, 0)
        rows[(2021, 2)] = (195, 0)
        rows[(2021, 3)] = (227, 0)
        rows[(2021, 4)] = (218, 0)
        rows[(2021, 5)] = (159, 6)  # end of reg + play-in + R1 starts
        rows[(2021, 6)] = (0, 44)
        rows[(2021, 7)] = (0, 31)  # Finals ended Jul 20
    else:
        # Normal seasons: Oct–Apr reg, Apr–Jun playoffs
        total_reg = 1230

        if season_year == 2023:
            # In-season tournament (NBA Cup) started 2023-24
            total_reg = 1230  # same total

        # Typical monthly distribution
        rows[(season_year, 10)] = (109, 0)
        rows[(season_year, 11)] = (210, 0)
        rows[(season_year, 12)] = (225, 0)
        rows[(season_year + 1, 1)] = (228, 0)
        rows[(season_year + 1, 2)] = (199, 0)
        rows[(season_year + 1, 3)] = (232, 0)
        remaining = total_reg - 109 - 210 - 225 - 228 - 199 - 232
        # ~27 reg games in Apr + play-in (~6) + R1 starts
        rows[(season_year + 1, 4)] = (max(remaining, 0), 20)
        rows[(season_year + 1, 5)] = (0, 40)
        rows[(season_year + 1, 6)] = (0, 24)

    return rows


# ── MLB schedule by month ────────────────────────────────────────────────
# Regular season: ~2430 games (162 x 30 / 2). Late Mar/Apr–Sep.
# Playoffs: Oct (+ sometimes early Nov for World Series).
# COVID 2020: 60-game season, Jul 23 – Sep 27, playoffs Sep-Oct.

def mlb_season(season_year):
    """Returns {(year,month): (reg_games, playoff_games, is_world_series)}."""
    rows = {}

    if season_year == 2020:
        # 60-game COVID season: 900 total games (60 x 30 / 2)
        rows[(2020, 7)] = (72, 0, False)  # started Jul 23
        rows[(2020, 8)] = (435, 0, False)
        rows[(2020, 9)] = (393, 8, False)  # expanded playoffs started Sep 29
        rows[(2020, 10)] = (0, 39, True)  # WS ended Oct 27
    else:
        # Normal season
        total_reg = 2430
        # Late March/early April start
        rows[(season_year, 3)] = (50, 0, False)  # last few days of March
        rows[(season_year, 4)] = (390, 0, False)
        rows[(season_year, 5)] = (420, 0, False)
        rows[(season_year, 6)] = (405, 0, False)
        rows[(season_year, 7)] = (390, 0, False)  # All-Star break
        rows[(season_year, 8)] = (420, 0, False)
        remaining = total_reg - 50 - 390 - 420 - 405 - 390 - 420
        rows[(season_year, 9)] = (remaining, 0, False)  # ~355
        # Playoffs: Oct (and sometimes Nov for WS)
        if season_year == 2020:
            pass  # handled above
        else:
            rows[(season_year, 10)] = (0, 45, True)
            # Some WS games occasionally in Nov
            rows[(season_year, 11)] = (0, 2, True) if season_year in (2022, 2024) else (0, 0, False)

    return rows


# ── NHL schedule by month ────────────────────────────────────────────────
# Regular season: 82 games x 32 teams / 2 = 1312 (31 teams before 2021-22 = 1271).
# Oct–Apr. Playoffs: Apr–Jun (~80 games).
# COVID 2019-20: suspended Mar 12 2020, resumed Aug 2020 in bubble.
# COVID 2020-21: 56-game season, Jan 13 – May 19 2021. Playoffs May-Jul 2021.

def nhl_season(season_year):
    """
    season_year is the start year (e.g. 2024 for 2024-25).
    Returns {(year,month): (reg_games, playoff_games)}.
    """
    rows = {}

    if season_year == 2019:
        # 2019-20: started Oct, suspended Mar 12, bubble Aug-Sep 2020
        rows[(2019, 10)] = (130, 0)
        rows[(2019, 11)] = (210, 0)
        rows[(2019, 12)] = (210, 0)
        rows[(2020, 1)] = (210, 0)
        rows[(2020, 2)] = (195, 0)
        rows[(2020, 3)] = (42, 0)  # ~8 days before suspension
        # Bubble: Aug 1 – Sep 28 2020
        rows[(2020, 8)] = (52, 28)  # qualifying round + R1
        rows[(2020, 9)] = (0, 43)  # R2, conf finals, SCF
    elif season_year == 2020:
        # 2020-21: 56-game season, Jan 13 – May 19
        total_reg = 868  # 56 x 31 / 2
        rows[(2021, 1)] = (115, 0)
        rows[(2021, 2)] = (195, 0)
        rows[(2021, 3)] = (210, 0)
        rows[(2021, 4)] = (210, 0)
        rows[(2021, 5)] = (138, 25)  # end reg + R1 starts
        rows[(2021, 6)] = (0, 40)
        rows[(2021, 7)] = (0, 20)  # SCF ended Jul 7
    else:
        # Normal seasons
        n_teams = 32 if season_year >= 2021 else 31
        total_reg = 82 * n_teams // 2

        rows[(season_year, 10)] = (130, 0)
        rows[(season_year, 11)] = (210, 0)
        rows[(season_year, 12)] = (210, 0)
        rows[(season_year + 1, 1)] = (210, 0)
        rows[(season_year + 1, 2)] = (190, 0)
        rows[(season_year + 1, 3)] = (210, 0)
        remaining = total_reg - 130 - 210 - 210 - 210 - 190 - 210
        rows[(season_year + 1, 4)] = (remaining, 20)  # end reg + R1 starts
        rows[(season_year + 1, 5)] = (0, 40)
        rows[(season_year + 1, 6)] = (0, 25)

    return rows


# ── NCAA Basketball (Men's D1) by month ──────────────────────────────────
# Season: Nov–Apr. ~5500 games. March Madness = 67 tournament games in Mar-Apr.
# COVID 2019-20: tournament cancelled Mar 2020.
# COVID 2020-21: tournament held but reduced.

def ncaab_season(season_year):
    """season_year = start year of academic year (2024 = 2024-25 season)."""
    rows = {}

    if season_year == 2019:
        # Tournament cancelled Mar 2020
        rows[(2019, 11)] = (1200, 0)
        rows[(2019, 12)] = (900, 0)
        rows[(2020, 1)] = (1000, 0)
        rows[(2020, 2)] = (1000, 0)
        rows[(2020, 3)] = (400, 0)  # conf tournaments started, then cancelled
    elif season_year == 2020:
        # Started late Nov 2020, tournament held Mar-Apr 2021
        rows[(2020, 11)] = (400, 0)  # late start
        rows[(2020, 12)] = (800, 0)
        rows[(2021, 1)] = (1000, 0)
        rows[(2021, 2)] = (1000, 0)
        rows[(2021, 3)] = (700, 32)  # conf tourneys + NCAA R1/R2
        rows[(2021, 4)] = (0, 35)  # Sweet 16 through Final Four + championship
    else:
        rows[(season_year, 11)] = (1200, 0)
        rows[(season_year, 12)] = (900, 0)
        rows[(season_year + 1, 1)] = (1000, 0)
        rows[(season_year + 1, 2)] = (1000, 0)
        rows[(season_year + 1, 3)] = (700, 32)  # conf tourneys + NCAA first/second round
        rows[(season_year + 1, 4)] = (0, 35)  # Sweet 16, Elite 8, Final Four, Championship

    return rows


# ── NCAA Football (FBS) by month ─────────────────────────────────────────
# Season: late Aug/Sep–Dec. ~800 FBS games. Bowl season: Dec-Jan.
# CFP: Dec-Jan (4 teams 2014-2023, expanded 12 teams 2024+).

def ncaaf_season(season_year):
    """season_year = the fall year."""
    rows = {}

    if season_year == 2020:
        # COVID: some conferences delayed, reduced schedules
        rows[(2020, 9)] = (60, 0)
        rows[(2020, 10)] = (160, 0)
        rows[(2020, 11)] = (180, 0)
        rows[(2020, 12)] = (100, 10)  # conf championships + early bowls
        rows[(2021, 1)] = (0, 20)  # remaining bowls + CFP
    else:
        rows[(season_year, 8)] = (40, 0)  # Week 0/1 (late Aug)
        rows[(season_year, 9)] = (200, 0)
        rows[(season_year, 10)] = (200, 0)
        rows[(season_year, 11)] = (200, 0)
        rows[(season_year, 12)] = (60, 20)  # conf championships + bowls
        rows[(season_year + 1, 1)] = (0, 25)  # remaining bowls + CFP/championship

    return rows


# ── Chicago team postseason appearances ──────────────────────────────────
# Format: {team: {season_year: [(year, month), ...]}}
# season_year = the primary year of the season (fall for NFL/NHL/NBA, summer for MLB)

CHICAGO_POSTSEASON = {
    "bears": {
        # 2018 season: lost WC to Eagles (Jan 6, 2019 — "Double Doink")
        2018: [(2019, 1)],
        # 2020 season: lost WC to Saints (Jan 10, 2021)
        2020: [(2021, 1)],
        # 2024 season: WC win vs Packers, Divisional loss to Rams (Jan 2025)
        2024: [(2025, 1)],
    },
    "bulls": {
        # 2021-22: lost first round to Bucks (Apr 2022)
        2021: [(2022, 4)],
        # 2022-23: lost play-in to Heat (Apr 2023) — play-in counts as postseason
        2022: [(2023, 4)],
    },
    "cubs": {
        # 2020: lost WC series to Marlins (Sep 30 – Oct 2, 2020)
        2020: [(2020, 9), (2020, 10)],
        # 2025: WC win vs Padres, NLDS loss to Brewers (Oct 2025)
        2025: [(2025, 10)],
    },
    "whitesox": {
        # 2020: WC series loss to A's (Sep 29 – Oct 1, 2020)
        2020: [(2020, 9), (2020, 10)],
        # 2021: ALDS loss to Astros (Oct 2021)
        2021: [(2021, 10)],
    },
    "blackhawks": {
        # 2019-20: bubble qualifying round win vs Oilers, R1 loss to Golden Knights (Aug 2020)
        2019: [(2020, 8)],
    },
}


def build_calendar():
    """Build the full monthly calendar DataFrame."""
    rows = []

    for year in range(2019, 2027):
        for month in range(1, 13):
            rows.append({"year": year, "month": month})

    df = pd.DataFrame(rows)

    # Initialize all columns to 0
    for col in [
        "nfl_games", "nba_games", "mlb_games", "nhl_games",
        "ncaab_games", "ncaaf_games",
        "nfl_playoff", "nba_playoff", "mlb_playoff", "nhl_playoff",
        "ncaab_postseason", "ncaaf_postseason",
        "super_bowl", "march_madness", "world_series",
        "bears_postseason", "bulls_postseason",
        "cubs_postseason", "whitesox_postseason", "blackhawks_postseason",
    ]:
        df[col] = 0

    # Fill NFL (include 2018 season for Jan-Feb 2019 playoffs/SB, 2026 for fall)
    for season in range(2018, 2027):
        for (y, m), (reg, playoff, is_sb) in nfl_season(season).items():
            if y < 2019:
                continue  # only keep 2019+ calendar rows
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "nfl_games"] += reg + playoff
            if playoff > 0:
                df.loc[mask, "nfl_playoff"] = 1
            if is_sb:
                df.loc[mask, "super_bowl"] = 1

    # Fill NBA (include 2018-19 for spring 2019, 2025-26 for fall 2026)
    for season in range(2018, 2027):
        for (y, m), (reg, playoff) in nba_season(season).items():
            if y < 2019:
                continue
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "nba_games"] += reg + playoff
            if playoff > 0:
                df.loc[mask, "nba_playoff"] = 1

    # Fill MLB
    for season in range(2019, 2027):
        for (y, m), (reg, playoff, is_ws) in mlb_season(season).items():
            if y > 2026:
                continue
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "mlb_games"] += reg + playoff
            if playoff > 0:
                df.loc[mask, "mlb_playoff"] = 1
            if is_ws:
                df.loc[mask, "world_series"] = 1

    # Fill NHL (include 2018-19 for spring 2019, 2025-26 for fall 2026)
    for season in range(2018, 2027):
        for (y, m), (reg, playoff) in nhl_season(season).items():
            if y < 2019:
                continue
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "nhl_games"] += reg + playoff
            if playoff > 0:
                df.loc[mask, "nhl_playoff"] = 1

    # Fill NCAA Basketball (include 2018-19 for Mar-Apr 2019, 2026-27 for Nov-Dec 2026)
    for season in range(2018, 2027):
        for (y, m), (reg, postseason) in ncaab_season(season).items():
            if y < 2019:
                continue
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "ncaab_games"] += reg + postseason
            if postseason > 0:
                df.loc[mask, "ncaab_postseason"] = 1

    # March Madness indicator (March-April when tournament is held)
    for year in range(2019, 2027):
        if year == 2020:
            continue  # cancelled
        df.loc[(df["year"] == year) & (df["month"].isin([3, 4])), "march_madness"] = 1

    # Fill NCAA Football (include 2018 for Jan 2019 bowls, and 2026 for fall 2026)
    for season in range(2018, 2027):
        for (y, m), (reg, postseason) in ncaaf_season(season).items():
            if y < 2019 or y > 2026:
                continue
            mask = (df["year"] == y) & (df["month"] == m)
            df.loc[mask, "ncaaf_games"] += reg + postseason
            if postseason > 0:
                df.loc[mask, "ncaaf_postseason"] = 1

    # Fill Chicago postseason
    for team, seasons in CHICAGO_POSTSEASON.items():
        col = f"{team}_postseason"
        for season_year, months in seasons.items():
            for y, m in months:
                mask = (df["year"] == y) & (df["month"] == m)
                df.loc[mask, col] = 1

    return df


def main():
    df = build_calendar()

    out_path = CLEAN_DIR / "calendar.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")

    # Summary
    print("\n--- Sample: Sep 2024 – Feb 2025 ---")
    sample = df[((df["year"] == 2024) & (df["month"] >= 9)) |
                ((df["year"] == 2025) & (df["month"] <= 2))]
    cols = ["year", "month", "nfl_games", "nba_games", "mlb_games", "nhl_games",
            "ncaab_games", "ncaaf_games", "super_bowl", "march_madness", "world_series"]
    print(sample[cols].to_string(index=False))

    # Verify no month has zero across all leagues (sanity)
    game_cols = ["nfl_games", "nba_games", "mlb_games", "nhl_games", "ncaab_games", "ncaaf_games"]
    zero_months = df[df[game_cols].sum(axis=1) == 0]
    print(f"\nMonths with zero games across all leagues: {len(zero_months)}")
    if len(zero_months) > 0:
        print(zero_months[["year", "month"]].to_string(index=False))

    # Chicago postseason summary
    print("\n--- Chicago postseason appearances ---")
    chi_cols = [c for c in df.columns if c.endswith("_postseason") and c.startswith(("bears", "bulls", "cubs", "whitesox", "blackhawks"))]
    chi = df[df[chi_cols].sum(axis=1) > 0][["year", "month"] + chi_cols]
    print(chi.to_string(index=False))


if __name__ == "__main__":
    main()
