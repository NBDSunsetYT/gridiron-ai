"""SYNTHETIC mechanical fixtures only. No NFL validation or forecasts implied."""
import csv
import io
import json
import random
import unittest

from .fit import REQUIRED, fit_csv
from .simulator import Evidence, evaluate_contract, simulate, simulate_game


def fixture_csv():
    output = io.StringIO()
    fields = sorted(REQUIRED | {"play_id", "availability"})
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for game in range(4):
        for team, defense in (("SYNTH-A", "SYNTH-B"), ("SYNTH-B", "SYNTH-A")):
            for index in range(160):
                down = index % 4 + 1
                kind = "pass" if down in (1, 3) else "rush" if down == 2 else "punt" if index % 8 else "field_goal"
                row = {key: "" for key in fields}
                row.update(game_id=f"SYNTHETIC-{game}", play_id=f"{team}-{index}", played_at=f"2024-01-{game+1:02}T12:00:00Z",
                           offense=team, defense=defense, down=down, yards_to_go=10, yardline_100=75 if index % 3 else 18,
                           seconds_remaining=1200 if index % 5 else 100, score_diff=0, play_type=kind,
                           yards_gained=12 if kind == "pass" else 5 if kind == "rush" else 0, elapsed_seconds=30,
                           drive_start=int(down == 1), complete_pass=int(kind == "pass"), interception=0, fumble_lost=0,
                           field_goal_made=1, punt_yards=40, turnover_return_yards=0, passer_id=team+"-QB" if kind == "pass" else "",
                           receiver_id=team+"-WR" if kind == "pass" else "", rusher_id=team+"-RB" if kind == "rush" else "",
                           availability=json.dumps({team+"-WR": "active", defense+"-WR": "active"}))
                writer.writerow(row)
            for index in range(8):
                row = dict(row)
                row.update(play_id=f"{team}-XP-{index}", play_type="extra_point", down=1, yards_gained=0,
                           complete_pass=0, passer_id="", receiver_id="", rusher_id="", drive_start=0)
                writer.writerow(row)
    return output.getvalue()


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture_csv()
        cls.model = fit_csv(cls.raw, "SYNTHETIC MECHANICAL TEST FIXTURE ONLY", "2024-02-01T00:00:00Z")["model"]

    def test_fit_rejects_lookahead_and_missing_evidence(self):
        with self.assertRaisesRegex(ValueError, "look-ahead"):
            fit_csv(self.raw, "SYNTHETIC", "2024-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "Missing CSV"):
            fit_csv("game_id\na\n", "SYNTHETIC", "2024-02-01T00:00:00Z")

    def test_correlated_passing_statistics_from_same_plays(self):
        evidence = Evidence(self.model, "SYNTH-A", "SYNTH-B")
        scores, players, totals, log = simulate_game(evidence, random.Random(4), ["SYNTH-A", "SYNTH-B"], trace=True)
        for team in ("SYNTH-A", "SYNTH-B"):
            self.assertEqual(players[team+"-QB"]["passingYards"], players[team+"-WR"]["receivingYards"])
            self.assertEqual(players[team+"-QB"]["completions"], players[team+"-WR"]["receptions"])
            self.assertEqual(players[team+"-QB"]["passingTouchdowns"], players[team+"-WR"]["receivingTouchdowns"])
        self.assertTrue(all(score >= 0 for score in scores))
        self.assertGreater(totals["plays"], 50)
        self.assertLess(totals["plays"], 600)
        self.assertTrue(log)

    def test_unknown_injury_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Insufficient evidence"):
            Evidence(self.model, "SYNTH-A", "SYNTH-B", {"playerId": "SYNTH-A-WR", "status": "inactive"})
        self.assertGreater(len(Evidence(self.model, "SYNTH-A", "SYNTH-B", {"playerId": "SYNTH-A-WR", "status": "active"}).rows), 100)

    def test_exact_threshold_and_push_settlement(self):
        c = {"kind": "total", "threshold": 40, "direction": "over"}
        self.assertIsNone(evaluate_contract(c, [20, 20], {}))
        self.assertFalse(evaluate_contract({**c, "equality": "no"}, [20, 20], {}))
        self.assertTrue(evaluate_contract(c, [21, 20], {}))

    def test_reproducibility_and_missing_event_cutoff(self):
        kwargs = dict(simulations=30, seed=12, event_start="2024-03-01T00:00:00Z")
        a = simulate(self.model, "SYNTH-A", "SYNTH-B", **kwargs)
        b = simulate(self.model, "SYNTH-A", "SYNTH-B", **kwargs)
        self.assertEqual(a["scoreDistributions"], b["scoreDistributions"])
        with self.assertRaisesRegex(ValueError, "eventStart"):
            simulate(self.model, "SYNTH-A", "SYNTH-B", simulations=1)

    def test_all_production_modes_complete_and_converge(self):
        reports = []
        for count in (10000, 50000, 100000):
            result = simulate(self.model, "SYNTH-A", "SYNTH-B", count, 42, "2024-03-01T00:00:00Z", [
                {"id": "receiver", "kind": "player", "playerId": "SYNTH-A-WR", "stat": "receivingYards", "threshold": 100.5, "direction": "over"},
                {"id": "passer", "kind": "player", "playerId": "SYNTH-A-QB", "stat": "passingYards", "threshold": 100.5, "direction": "over"}])
            self.assertEqual(result["simulations"], count)
            self.assertAlmostEqual(result["homeWinProbability"] + result["awayWinProbability"] + result["tieProbability"], 1)
            self.assertEqual(sum(x["count"] for x in result["jointOutcomes"]), count)
            self.assertTrue(all(x["outcomes"][0] == x["outcomes"][1] for x in result["jointOutcomes"]))
            self.assertIsNone(result["uncertainty"]["modelInterval"])
            self.assertEqual(result["convergence"][-1]["simulations"], count)
            self.assertLess(len(json.dumps(result)), 2_000_000)
            self.assertNotIn('games', result)
            self.assertLessEqual(len(result['representativeGames']), 3)
            self.assertFalse(result['runManifest']['storage']['allGamesRetained'])
            self.assertFalse(result['runManifest']['storage']['allPlaysRetained'])
            self.assertTrue(all(pair['games']==count for pair in result['correlations']))
            reports.append(result)
        # Mechanical convergence check, not an accuracy claim or a tight flaky threshold.
        self.assertLess(abs(reports[0]["homeWinProbability"] - reports[-1]["homeWinProbability"]), .03)
        self.assertGreater(reports[0]["convergence"][-1]["monteCarloSE"], reports[-1]["convergence"][-1]["monteCarloSE"])


if __name__ == "__main__":
    unittest.main()


class MechanicalEvidence:
    """Deterministic SYNTHETIC events for rule tests; never used as a fitted model."""
    def __init__(self, kind, yards=0):
        self.kind, self.yards = kind, yards
    def start(self, rng, team):
        return 75
    def conversion(self, rng, team, diff, late):
        return 1
    def sample(self, rng, team, defense, down, field, distance, diff, clock):
        return {"kind": self.kind, "yards": self.yards, "elapsed": 90, "qb": team+"-QB", "receiver": team+"-WR", "runner": team+"-RB", "complete": int(self.kind == "pass"), "int": 0, "fumble": 0, "fg": 1, "punt": 50, "return": 0}


class ScoringTests(unittest.TestCase):
    def test_touchdowns_and_conversions_are_seven_not_six(self):
        scores, players, totals, _ = simulate_game(MechanicalEvidence("pass", 99), random.Random(1), ["SYNTH-A", "SYNTH-B"])
        self.assertTrue(all(score % 7 == 0 for score in scores))
        self.assertEqual(sum(scores), totals["touchdowns"] * 7)
        self.assertEqual(sum(p["passingTouchdowns"] for p in players.values()), totals["touchdowns"])
        self.assertEqual(sum(p["receivingTouchdowns"] for p in players.values()), totals["touchdowns"])
        self.assertGreater(totals["overtime"], 0)

    def test_field_goals_are_three_and_punts_do_not_score(self):
        scores, _, totals, _ = simulate_game(MechanicalEvidence("field_goal"), random.Random(1), ["SYNTH-A", "SYNTH-B"])
        self.assertEqual(sum(scores), totals["fieldGoals"] * 3)
        scores, _, totals, _ = simulate_game(MechanicalEvidence("punt"), random.Random(1), ["SYNTH-A", "SYNTH-B"])
        self.assertEqual(scores, [0, 0])
        self.assertGreater(totals["punts"], 0)

    def test_safeties_score_two_and_end_overtime(self):
        scores, _, totals, _ = simulate_game(MechanicalEvidence("sack", -99), random.Random(1), ["SYNTH-A", "SYNTH-B"])
        self.assertEqual(sum(scores), totals["safeties"] * 2)
        self.assertNotEqual(scores[0], scores[1])
        self.assertGreater(totals["sacks"], 0)

    def test_turnover_returns_are_linked_defensive_touchdowns(self):
        class Turnovers(MechanicalEvidence):
            def sample(self, *args):
                p = super().sample(*args)
                p.update(complete=0, int=1, **{"return": 100})
                return p
        scores, players, totals, _ = simulate_game(Turnovers("pass"), random.Random(1), ["SYNTH-A", "SYNTH-B"])
        self.assertEqual(sum(scores), totals["defensiveTouchdowns"] * 7)
        self.assertEqual(sum(p["interceptions"] for p in players.values()), totals["defensiveTouchdowns"])
        self.assertEqual(sum(p["receivingYards"] for p in players.values()), 0)
