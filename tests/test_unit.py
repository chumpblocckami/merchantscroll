import json
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import (
    canonical_starttime,
    extract_date,
    minify_tournament_data,
    normalize_date,
)

SAMPLE_DECK = json.load(open("tests/assets/sample_deck.json"))

SAMPLE_TOURNAMENT = {
    "event_id": "12345",
    "description": "Pauper League",
    "starttime": "2026-06-05",
    "site_name": "pauper-league-2026-06-0510636",
    "player_count": {},
    "decklists": [SAMPLE_DECK],
}


class TestMinifyTournamentData(unittest.TestCase):
    def test_preserves_top_level_fields(self):
        result = minify_tournament_data(SAMPLE_TOURNAMENT)
        self.assertEqual(result["description"], "Pauper League")
        self.assertEqual(result["starttime"], "2026-06-05")
        self.assertEqual(result["site_name"], "pauper-league-2026-06-0510636")

    def test_preserves_player(self):
        result = minify_tournament_data(SAMPLE_TOURNAMENT)
        self.assertEqual(len(result["decklists"]), 1)
        self.assertEqual(result["decklists"][0]["player"], "__forge__")

    def test_preserves_card_name_and_type(self):
        result = minify_tournament_data(SAMPLE_TOURNAMENT)
        deck = result["decklists"][0]
        card = deck["main_deck"][0]
        self.assertIn("card_name", card["card_attributes"])
        self.assertIn("card_type", card["card_attributes"])
        self.assertTrue(len(card["card_attributes"]["card_name"]) > 0)

    def test_strips_extra_card_metadata(self):
        result = minify_tournament_data(SAMPLE_TOURNAMENT)
        card = result["decklists"][0]["main_deck"][0]
        attrs = card["card_attributes"]
        self.assertNotIn("rarity", attrs)
        self.assertNotIn("color", attrs)
        self.assertNotIn("cardset", attrs)
        self.assertNotIn("digitalobjectcatalogid", attrs)

    def test_preserves_qty(self):
        result = minify_tournament_data(SAMPLE_TOURNAMENT)
        card = result["decklists"][0]["main_deck"][0]
        self.assertIn("qty", card)

    def test_preserves_wins_when_present(self):
        deck_with_wins = {**SAMPLE_DECK, "wins": {"wins": 5, "losses": 0}}
        data = {**SAMPLE_TOURNAMENT, "decklists": [deck_with_wins]}
        result = minify_tournament_data(data)
        self.assertEqual(result["decklists"][0]["wins"], {"wins": 5, "losses": 0})

    def test_omits_wins_when_absent(self):
        deck_no_wins = {k: v for k, v in SAMPLE_DECK.items() if k != "wins"}
        data = {**SAMPLE_TOURNAMENT, "decklists": [deck_no_wins]}
        result = minify_tournament_data(data)
        self.assertNotIn("wins", result["decklists"][0])


class TestExtractDate(unittest.TestCase):
    def test_extracts_date_from_url(self):
        url = "https://www.mtgo.com/decklist/pauper-league-2026-06-0510636"
        self.assertEqual(extract_date(url), "2026-06-05")

    def test_returns_fallback_for_no_date(self):
        self.assertEqual(extract_date("no-date-here"), "0000-00-00")


class TestCanonicalStarttime(unittest.TestCase):
    def test_league_uses_site_name_date(self):
        self.assertEqual(
            canonical_starttime(
                "pauper-league-2025-11-2310636", "2026-06-17"
            ),
            "2025-11-23",
        )

    def test_challenge_keeps_starttime(self):
        self.assertEqual(
            canonical_starttime(
                "pauper-challenge-32-2026-06-1412844338",
                "2026-06-14 17:00:00.0",
            ),
            "2026-06-14 17:00:00.0",
        )

    def test_minify_applies_canonical_league_date(self):
        data = {
            **SAMPLE_TOURNAMENT,
            "site_name": "pauper-league-2025-11-2310636",
            "starttime": "2026-06-17",
        }
        result = minify_tournament_data(data)
        self.assertEqual(result["starttime"], "2025-11-23")


class TestRefreshPolicy(unittest.TestCase):
    def test_active_league_within_week(self):
        from datetime import date

        from src.refresh_policy import is_active_league

        self.assertTrue(
            is_active_league(
                "pauper-league-2026-06-1710636",
                today=date(2026, 6, 19),
            )
        )
        self.assertFalse(
            is_active_league(
                "pauper-league-2026-06-1010636",
                today=date(2026, 6, 19),
            )
        )

    def test_should_crawl_empty_recent_challenge(self):
        from datetime import date

        from src.refresh_policy import should_crawl_mtgo

        self.assertTrue(
            should_crawl_mtgo(
                "pauper-challenge-32-2026-06-1812844831",
                exists=True,
                stored_deck_count=0,
                today=date(2026, 6, 19),
            )
        )
        self.assertFalse(
            should_crawl_mtgo(
                "pauper-challenge-32-2026-05-1012842105",
                exists=True,
                stored_deck_count=0,
                today=date(2026, 6, 19),
            )
        )

    def test_should_crawl_active_league_with_decks(self):
        from datetime import date

        from src.refresh_policy import should_crawl_mtgo

        self.assertTrue(
            should_crawl_mtgo(
                "pauper-league-2026-06-1710636",
                exists=True,
                stored_deck_count=24,
                today=date(2026, 6, 19),
            )
        )
        self.assertFalse(
            should_crawl_mtgo(
                "pauper-challenge-32-2026-06-1412844338",
                exists=True,
                stored_deck_count=32,
                today=date(2026, 6, 19),
            )
        )

    def test_save_tournament_if_nonempty(self):
        import tempfile
        from pathlib import Path

        from src.refresh_policy import save_tournament_if_nonempty

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            site = "pauper-challenge-empty"
            empty = {
                "site_name": site,
                "description": "Empty",
                "decklists": [],
            }
            changed, count = save_tournament_if_nonempty(raw, site, empty)
            self.assertFalse(changed)
            self.assertEqual(count, 0)
            self.assertFalse((raw / f"{site}.json").exists())

            (raw / f"{site}.json").write_text('{"decklists": []}')
            changed, count = save_tournament_if_nonempty(raw, site, empty)
            self.assertTrue(changed)
            self.assertEqual(count, 0)
            self.assertFalse((raw / f"{site}.json").exists())

            full = {**empty, "decklists": [{"player": "alice", "main_deck": []}]}
            changed, count = save_tournament_if_nonempty(raw, site, full)
            self.assertTrue(changed)
            self.assertEqual(count, 1)
            self.assertTrue((raw / f"{site}.json").exists())


class TestNormalizeDate(unittest.TestCase):
    def test_iso_date(self):
        self.assertEqual(normalize_date("2026-06-05"), "2026-06-05")

    def test_datetime_with_time(self):
        self.assertEqual(normalize_date("2026-06-05 19:00:00"), "2026-06-05")

    def test_datetime_with_microseconds(self):
        self.assertEqual(normalize_date("2026-06-05 19:00:00.000"), "2026-06-05")



class TestDeckStats(unittest.TestCase):
    def test_archetype_slug(self):
        from src.deck_stats import archetype_slug

        self.assertEqual(archetype_slug("U Terror"), "u-terror")
        self.assertEqual(archetype_slug("  Altar Tron  "), "altar-tron")

    def test_rebuild_deck_profiles(self):
        import tempfile
        from pathlib import Path

        from src.deck_stats import rebuild_deck_profiles

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            out = Path(tmp) / "decks"
            raw.mkdir()

            league = {
                "description": "Pauper League",
                "starttime": "2026-06-05",
                "site_name": "pauper-league-2026-06-0510636",
                "decklists": [
                    {
                        "player": "alice",
                        "archetype": "U Terror",
                        "colors": ["U", "R"],
                        "wins": {"wins": "5", "losses": "0"},
                    },
                    {
                        "player": "bob",
                        "archetype": "U Terror",
                        "colors": ["U", "R"],
                        "wins": {"wins": "5", "losses": "0"},
                    },
                ],
            }
            challenge = {
                "description": "Pauper Challenge",
                "starttime": "2026-06-14 17:00:00.0",
                "site_name": "pauper-challenge-32-2026-06-1412844338",
                "decklists": [
                    {
                        "player": "alice",
                        "archetype": "U Terror",
                        "colors": ["U", "R"],
                        "wins": {"wins": 3, "losses": 2},
                    }
                ],
            }
            (raw / "league.json").write_text(__import__("json").dumps(league))
            (raw / "challenge.json").write_text(__import__("json").dumps(challenge))

            count = rebuild_deck_profiles(raw_dir=raw, profiles_dir=out)
            self.assertEqual(count, 1)

            profile = __import__("json").loads((out / "u-terror.json").read_text())
            stats = profile["stats"]
            self.assertEqual(stats["total_entries"], 3)
            self.assertEqual(stats["league_entries"], 2)
            self.assertEqual(stats["league_trophies"], 2)
            self.assertEqual(stats["challenge_appearances"], 1)
            self.assertEqual(stats["challenge_wins"], 3)
            self.assertEqual(stats["challenge_losses"], 2)
            self.assertEqual(profile["top_pilots"][0]["player"], "alice")
            self.assertEqual(profile["top_pilots"][0]["count"], 2)

    def test_archetype_alias_merge(self):
        import tempfile
        from pathlib import Path

        from src.deck_stats import rebuild_deck_profiles

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            out = Path(tmp) / "decks"
            raw.mkdir()
            data = {
                "site_name": "pauper-league-2026-06-0510636",
                "description": "Pauper League",
                "starttime": "2026-06-05",
                "decklists": [
                    {"player": "a", "archetype": "White Weenie", "colors": ["W"], "wins": {"wins": "5", "losses": "0"}},
                    {"player": "b", "archetype": "White Weennie", "colors": ["W"], "wins": {"wins": "5", "losses": "0"}},
                ],
            }
            (raw / "league.json").write_text(__import__("json").dumps(data))
            self.assertEqual(rebuild_deck_profiles(raw_dir=raw, profiles_dir=out), 1)
            profile = __import__("json").loads((out / "white-weenie.json").read_text())
            self.assertEqual(profile["stats"]["total_entries"], 2)
            self.assertFalse((out / "white-weennie.json").exists())

if __name__ == "__main__":
    unittest.main()
