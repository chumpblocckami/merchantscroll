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


class TestClassifyAndNormalize(unittest.TestCase):
    def test_classify_unlabeled_mtgo_deck(self):
        import tempfile
        from pathlib import Path

        from src.classifier import classify_and_normalize_labels

        archetype_map = {
            "Mono Blue Terror": ["Tolarian Terror", "Counterspell", "Thought Scour"],
        }
        tournament = {
            "site_name": "pauper-league-test",
            "decklists": [
                {
                    "player": "alice",
                    "main_deck": [
                        {
                            "qty": "4",
                            "card_attributes": {
                                "card_name": "Tolarian Terror",
                                "card_type": "ISCREA",
                            },
                        },
                        {
                            "qty": "4",
                            "card_attributes": {
                                "card_name": "Counterspell",
                                "card_type": "INSTNT",
                            },
                        },
                        {
                            "qty": "4",
                            "card_attributes": {
                                "card_name": "Thought Scour",
                                "card_type": "SORCRY",
                            },
                        },
                    ],
                    "sideboard_deck": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "pauper-league-test.json").write_text(
                __import__("json").dumps(tournament)
            )
            classified, normalized = classify_and_normalize_labels(
                archetype_map, raw_dir=raw
            )
            self.assertEqual(classified, 1)
            self.assertEqual(normalized, 0)
            saved = __import__("json").loads(
                (raw / "pauper-league-test.json").read_text()
            )
            self.assertEqual(saved["decklists"][0]["archetype"], "Mono Blue Terror")


def _deck(*card_names):
    return {
        "main_deck": [
            {"qty": "4", "card_attributes": {"card_name": name, "card_type": "ISCREA"}}
            for name in card_names
        ],
        "sideboard_deck": [],
    }


class TestCardNameNormalization(unittest.TestCase):
    def test_front_face_matches_full_dfc_signature(self):
        from src.classifier import classify_deck

        # Pauperwave and the dataset spell out both faces, MTGO only the front.
        archetype_map = {
            "Izzet Delver": [
                "Delver of Secrets // Insectile Aberration",
                "Counterspell",
                "Lightning Bolt",
            ]
        }
        deck = _deck("Delver of Secrets", "Counterspell", "Lightning Bolt")
        self.assertEqual(classify_deck(deck, archetype_map), "Izzet Delver")

    def test_basics_are_not_signal_but_nonbasic_lands_are(self):
        from src.classifier import _main_deck_card_names

        names = _main_deck_card_names(
            _deck("Island", "Snow-Covered Mountain", "Urza's Tower", "Ponder")
        )
        self.assertEqual(names, {"Urza's Tower", "Ponder"})


class TestMatchArchetype(unittest.TestCase):
    def test_tie_goes_to_the_earlier_dictionary_entry(self):
        from src.classifier import match_archetype

        # Both score 1.0; the popular archetype is listed first and must win.
        archetype_map = {
            "Grixis Affinity": ["Myr Enforcer", "Thoughtcast", "Galvanic Blast"],
            "Dimir Affinity": ["Myr Enforcer", "Thoughtcast", "Galvanic Blast"],
        }
        cards = {"Myr Enforcer", "Thoughtcast", "Galvanic Blast"}
        name, score = match_archetype(cards, archetype_map)
        self.assertEqual(name, "Grixis Affinity")
        self.assertEqual(score, 1.0)

        reordered = dict(reversed(list(archetype_map.items())))
        self.assertEqual(match_archetype(cards, reordered)[0], "Dimir Affinity")

    def test_no_signature_beats_the_threshold(self):
        from src.classifier import classify_deck

        archetype_map = {"Elves": ["Llanowar Elves", "Timberwatch Elf", "Priest of Titania"]}
        self.assertIsNone(classify_deck(_deck("Ponder", "Brainstorm"), archetype_map))


class TestBuildSignatureMap(unittest.TestCase):
    def test_prefers_distinctive_cards_over_shared_staples(self):
        from src.classifier import build_signature_map

        # Lightning Bolt is in every deck of both archetypes, so it carries no
        # signal even though it is the most frequent card.
        arch_decks = {
            "Burn": [
                {"Lightning Bolt", "Fireblast", "Chain Lightning"},
                {"Lightning Bolt", "Fireblast", "Chain Lightning"},
            ],
            "Delver": [
                {"Lightning Bolt", "Delver of Secrets", "Counterspell"},
                {"Lightning Bolt", "Delver of Secrets", "Counterspell"},
            ],
        }
        result = build_signature_map(arch_decks, top_n=2, min_sigs=2)
        self.assertNotIn("Lightning Bolt", result["Burn"])
        self.assertEqual(set(result["Burn"]), {"Fireblast", "Chain Lightning"})

    def test_orders_archetypes_by_deck_count(self):
        from src.classifier import build_signature_map

        arch_decks = {
            "Fringe": [{"Ornithopter", "Frogmite", "Somber Hoverguard"}] * 2,
            "Popular": [{"Ponder", "Brainstorm", "Counterspell"}] * 9,
        }
        self.assertEqual(list(build_signature_map(arch_decks)), ["Popular", "Fringe"])


class TestMergeArchetypeDictionaries(unittest.TestCase):
    def test_baseline_wins_and_mined_entries_are_appended(self):
        from src.classifier import merge_archetype_dictionaries

        baseline = {"Elves": ["Timberwatch Elf", "Priest of Titania", "Birchlore Rangers"]}
        derived = {
            "Elves": ["Llanowar Elves", "Fyndhorn Elves", "Elvish Mystic"],
            "Local Brew": ["Squadron Hawk", "Kor Skyfisher", "Battle Screech"],
        }
        merged = merge_archetype_dictionaries(baseline, derived)

        self.assertEqual(merged["Elves"], baseline["Elves"])
        self.assertEqual(list(merged), ["Elves", "Local Brew"])

    def test_rebuild_merges_baseline_with_pauperwave_data(self):
        import tempfile
        from pathlib import Path

        from src.classifier import rebuild_archetype_dictionary

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw = tmp_path / "raw"
            raw.mkdir()
            baseline_path = tmp_path / "paupergeddon.json"
            baseline_path.write_text(
                json.dumps({"Elves": ["Timberwatch Elf", "Priest of Titania", "Quirion Ranger"]})
            )

            local = _deck("Squadron Hawk", "Kor Skyfisher", "Battle Screech", "Prismatic Strands")
            local["archetype"] = "Local Brew"
            (raw / "pauperwave-event.json").write_text(
                json.dumps({"site_name": "pauperwave-event", "decklists": [local, dict(local)]})
            )

            out_path = tmp_path / "pauperwave.json"
            merged = rebuild_archetype_dictionary(
                raw, baseline_path=baseline_path, output_path=out_path
            )

            self.assertEqual(list(merged), ["Elves", "Local Brew"])
            self.assertEqual(merged["Elves"][0], "Timberwatch Elf")
            self.assertEqual(json.loads(out_path.read_text()), merged)


class TestFrontendClassifierParity(unittest.TestCase):
    """index.html reimplements classify_deck; the two must not drift apart."""

    def test_javascript_matches_python(self):
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        if shutil.which("node") is None:
            self.skipTest("node is not installed")

        from src.classifier import _main_deck_card_names, match_archetype

        archetype_map = {
            "Grixis Affinity": [
                "Myr Enforcer",
                "Thoughtcast",
                "Galvanic Blast",
                "Seat of the Synod",
            ],
            "Izzet Delver": [
                "Delver of Secrets // Insectile Aberration",
                "Counterspell",
                "Lightning Bolt",
                "Ponder",
            ],
            "Dimir Affinity": ["Myr Enforcer", "Thoughtcast", "Galvanic Blast", "Ponder"],
        }
        decks = [
            _deck("Myr Enforcer", "Thoughtcast", "Galvanic Blast", "Ponder"),
            _deck("Delver of Secrets", "Counterspell", "Lightning Bolt", "Ponder"),
            _deck("Island", "Snow-Covered Island", "Ponder"),
            _deck("Myr Enforcer", "Thoughtcast", "Galvanic Blast", "Seat of the Synod"),
        ]
        expected = []
        for deck in decks:
            name, score = match_archetype(_main_deck_card_names(deck), archetype_map)
            expected.append(name if score >= 0.5 else "")

        html = Path("index.html").read_text()
        start = html.index("const BASIC_LANDS = new Set(")
        end = html.index("/* ── Card preview ── */")
        script = f"""
const archetypeMap = {json.dumps(archetype_map)};
{html[start:end]}
const decks = {json.dumps(decks)};
console.log(JSON.stringify(decks.map(classifyDeck)));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(script)
            script_path = fh.name
        try:
            out = subprocess.run(
                ["node", script_path], capture_output=True, text=True, check=True
            )
        finally:
            os.unlink(script_path)

        self.assertEqual(json.loads(out.stdout), expected)


class TestRequiredColors(unittest.TestCase):
    def test_phyrexian_mana_is_not_a_color_requirement(self):
        from src.scryfall import required_colors

        # {R/P} costs 2 life instead, so a blue deck can play Gut Shot.
        self.assertEqual(required_colors({"name": "Gut Shot", "mana_cost": "{R/P}"}), [])
        self.assertEqual(
            required_colors({"name": "Apostle's Blessing", "mana_cost": "{1}{W/P}"}), []
        )

    def test_monocolored_hybrid_is_not_a_color_requirement(self):
        from src.scryfall import required_colors

        self.assertEqual(required_colors({"name": "Flame Javelin", "mana_cost": "{2/R}{2/R}"}), [])

    def test_color_in_an_ability_is_ignored(self):
        from src.scryfall import required_colors

        # Nihil Spellbomb costs {1}; its {B} lives in an optional draw trigger.
        self.assertEqual(required_colors({"name": "Nihil Spellbomb", "mana_cost": "{1}"}), [])

    def test_colorless_card_with_colored_cost_still_requires_it(self):
        from src.scryfall import required_colors

        # Writhing Chrysalis prints as colorless but costs {2}{R}{G}.
        card = {"name": "Writhing Chrysalis", "mana_cost": "{2}{R}{G}", "colors": []}
        self.assertEqual(required_colors(card), ["G", "R"])

    def test_both_faces_count(self):
        from src.scryfall import required_colors

        card = {
            "name": "Fire // Ice",
            "card_faces": [{"mana_cost": "{1}{R}"}, {"mana_cost": "{1}{U}"}],
        }
        self.assertEqual(required_colors(card), ["R", "U"])

    def test_cards_never_cast_contribute_nothing(self):
        from src.scryfall import required_colors

        card = {"name": "Sneaky Snacker", "mana_cost": "{U}{B}"}
        self.assertEqual(required_colors(card), [])


class TestNameVariants(unittest.TestCase):
    def test_split_card_spellings(self):
        from src.scryfall import _name_variants

        self.assertEqual(
            _name_variants("Fire // Ice"),
            {"Fire // Ice", "Fire/Ice", "Fire", "Ice"},
        )

    def test_mojibake_spelling_is_registered(self):
        from src.scryfall import _name_variants

        # MTGO serves this name as UTF-8 bytes reread as Latin-1.
        self.assertIn("Troll of Khazad-dÃ»m", _name_variants("Troll of Khazad-dûm"))

    def test_plain_name_has_no_extra_variants(self):
        from src.scryfall import _name_variants

        self.assertEqual(_name_variants("Counterspell"), {"Counterspell"})


class TestIsPlayable(unittest.TestCase):
    def test_art_series_and_playtest_cards_are_skipped(self):
        from src.scryfall import _is_playable

        art = {"name": "Delver of Secrets // Delver of Secrets", "legalities": {"pauper": "not_legal"}}
        real = {"name": "Counterspell", "legalities": {"pauper": "legal", "modern": "not_legal"}}
        self.assertFalse(_is_playable(art))
        self.assertTrue(_is_playable(real))


class TestEnrichDeckColors(unittest.TestCase):
    def _tournament(self, main, sideboard=()):
        def entry(name, card_type="ISCREA", colors=None):
            attrs = {"card_name": name, "card_type": card_type}
            if colors is not None:
                attrs["colors"] = colors
            return {"qty": "4", "card_attributes": attrs}

        return {
            "decklists": [
                {
                    "main_deck": [entry(*c) if isinstance(c, tuple) else entry(c) for c in main],
                    "sideboard_deck": [entry(c) for c in sideboard],
                }
            ]
        }

    def test_sideboard_does_not_recolor_the_deck(self):
        from src.utils import enrich_deck_colors

        lookup = {"Tolarian Terror": ["U"], "Counterspell": ["U"], "Lightning Bolt": ["R"]}
        data = self._tournament(["Tolarian Terror", "Counterspell"], ["Lightning Bolt"])
        enrich_deck_colors(data, lookup)
        self.assertEqual(data["decklists"][0]["colors"], ["U"])

    def test_lands_are_excluded(self):
        from src.utils import enrich_deck_colors

        lookup = {"Ponder": ["U"], "Bojuka Bog": ["B"]}
        data = self._tournament([("Ponder",), ("Bojuka Bog", "LAND  ")])
        enrich_deck_colors(data, lookup)
        self.assertEqual(data["decklists"][0]["colors"], ["U"])

    def test_colorless_deck_gets_c(self):
        from src.utils import enrich_deck_colors

        data = self._tournament(["Gut Shot"])
        enrich_deck_colors(data, {"Gut Shot": []})
        self.assertEqual(data["decklists"][0]["colors"], ["C"])

    def test_unknown_card_falls_back_to_mtgo_colors(self):
        from src.utils import enrich_deck_colors

        # A card too new for the cached Scryfall data still shows its color.
        data = self._tournament([("Darval, Whose Web Protects", "ISCREA", ["COLOR_WHITE"])])
        enrich_deck_colors(data, {})
        self.assertEqual(data["decklists"][0]["colors"], ["W"])

    def test_known_colorless_card_does_not_fall_back(self):
        from src.utils import enrich_deck_colors

        # Gut Shot is in the lookup as [], so MTGO calling it red must not win.
        data = self._tournament([("Gut Shot", "INSTNT", ["COLOR_RED"])])
        enrich_deck_colors(data, {"Gut Shot": []})
        self.assertEqual(data["decklists"][0]["colors"], ["C"])


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
                        "archetype": "Mono Blue Terror",
                        "colors": ["U", "R"],
                        "wins": {"wins": "5", "losses": "0"},
                    },
                    {
                        "player": "bob",
                        "archetype": "Mono Blue Terror",
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
                        "archetype": "Mono Blue Terror",
                        "colors": ["U", "R"],
                        "wins": {"wins": 3, "losses": 2},
                    }
                ],
            }
            (raw / "league.json").write_text(__import__("json").dumps(league))
            (raw / "challenge.json").write_text(__import__("json").dumps(challenge))

            count = rebuild_deck_profiles(raw_dir=raw, profiles_dir=out)
            self.assertEqual(count, 1)

            profile = __import__("json").loads((out / "mono-blue-terror.json").read_text())
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

PAUPERWAVE_LISTING = [
    {"name": "2026-07-11-paupergeddon.md"},
    {"name": "0000-template.md"},
    {"name": "readme.txt"},
]


class TestPauperwaveTokenFallback(unittest.TestCase):
    """A rejected token must not stop the listing of a public repo."""

    def _fake_get(self, status_for_auth):
        class FakeResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"{self.status_code} Client Error")

        calls = []

        def fake_get(url, headers=None, timeout=None):
            authed = "Authorization" in (headers or {})
            calls.append(headers.get("Authorization") if authed else None)
            if authed and status_for_auth >= 400:
                return FakeResponse(status_for_auth, {"message": "Bad credentials"})
            return FakeResponse(200, PAUPERWAVE_LISTING)

        return fake_get, calls

    def test_falls_back_to_anonymous_on_401(self):
        from unittest.mock import patch

        from src import pauperwave_crawler

        fake_get, calls = self._fake_get(401)
        with patch.object(pauperwave_crawler.requests, "get", fake_get):
            files = pauperwave_crawler.discover_pauperwave_files(token="expired")

        self.assertEqual(calls, ["token expired", None])
        self.assertEqual([f["name"] for f in files], ["2026-07-11-paupergeddon.md"])

    def test_token_whitespace_is_stripped(self):
        from unittest.mock import patch

        from src import pauperwave_crawler

        fake_get, calls = self._fake_get(200)
        with patch.object(pauperwave_crawler.requests, "get", fake_get):
            pauperwave_crawler.discover_pauperwave_files(token="  ghp_valid\n")

        self.assertEqual(calls, ["token ghp_valid"])


class TestMtgoDiscovery(unittest.TestCase):
    """A listing without decklist links is a failure, not an empty schedule."""

    LISTING_HTML = """
    <html><body>
      <a href="/decklist/pauper-league-2026-07-3010855">Pauper League</a>
      <a href="/decklist/modern-league-2026-07-3010860">Modern League</a>
      <a href="/decklist/pauper-league-2026-07-3010855">dup</a>
      <a href="/about">About</a>
    </body></html>
    """

    STUB_HTML = "<html><head><title>Access Denied</title></head><body></body></html>"

    def _patch_get(self, html, status=200):
        from unittest.mock import patch

        from src import crawler

        class FakeResponse:
            status_code = status
            text = html
            content = html.encode()

        return patch.object(crawler.requests, "get", lambda *a, **kw: FakeResponse())

    def test_extracts_unique_absolute_urls(self):
        from src.crawler import crawl_tournaments

        with self._patch_get(self.LISTING_HTML):
            urls = crawl_tournaments()

        self.assertEqual(
            urls,
            [
                "https://www.mtgo.com/decklist/modern-league-2026-07-3010860",
                "https://www.mtgo.com/decklist/pauper-league-2026-07-3010855",
            ],
        )

    def test_stub_page_raises_with_diagnostics(self):
        from src.crawler import EmptyListingError, crawl_tournaments

        with self._patch_get(self.STUB_HTML), self.assertRaises(EmptyListingError) as ctx:
            crawl_tournaments(attempts=1)

        message = str(ctx.exception)
        self.assertIn("Access Denied", message)
        self.assertIn("bytes", message)


if __name__ == "__main__":
    unittest.main()
