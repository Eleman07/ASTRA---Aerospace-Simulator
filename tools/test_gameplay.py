"""Career mission catalog and objective evaluation tests."""
from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from astra.gameplay import GameSession, find_mission, mission_catalog
from desktop_runtime import DesktopRuntime


class GiocaCareerTests(unittest.TestCase):
    def test_gioca_has_three_activities_and_three_missions_per_career_category(self):
        catalog = mission_catalog()
        self.assertEqual(set(catalog), {"space", "aircraft", "drone"})
        self.assertEqual([len(catalog[key]) for key in ("space", "aircraft", "drone")], [6, 3, 3])
        missions = [mission for rows in catalog.values() for mission in rows]
        self.assertEqual(len({mission["id"] for mission in missions}), 12)
        self.assertEqual(Counter(item["category"] for item in missions), {
            "INGEGNERIA": 3, "ESPLORAZIONE": 3,
            "PILOTAGGIO": 3, "SCIENZA": 3,
        })
        self.assertEqual([mission["campaign"] for mission in catalog["space"]], [
            "FRONTIERA BLU · I / VI", "FRONTIERA BLU · II / VI",
            "FRONTIERA BLU · III / VI", "FRONTIERA BLU · IV / VI",
            "FRONTIERA BLU · V / VI", "FRONTIERA BLU · VI / VI",
        ])

    def test_aircraft_circuit_requires_real_altitude_distance_and_touchdown(self):
        session = GameSession()
        session.start("air_blue_line")
        session.update({"time_s": 0, "mission_started": True, "altitude_m": 0,
                        "phase": "TAKEOFF", "position_ned_m": [0, 0, 0]}, .1)
        halfway = session.update({"time_s": 20, "mission_started": True,
                                  "altitude_m": 800, "phase": "CRUISE",
                                  "position_ned_m": [0, 13000, -800]}, 20)
        self.assertTrue(halfway["progress"]["altitude"])
        self.assertTrue(halfway["progress"]["distance"])
        self.assertFalse(halfway["complete"])
        result = session.update({"time_s": 45, "mission_started": True,
            "altitude_m": 0, "phase": "LANDED", "position_ned_m": [0, 13000, 0],
            "mission_metrics": {"touchdown_speed_m_s": 25}}, 25)
        self.assertTrue(result["progress"]["safe_landing"])
        self.assertTrue(result["complete"])

    def test_drone_hold_objective_must_be_continuous(self):
        session = GameSession()
        session.start("drone_grid")
        state = {"mission_started": True, "altitude_m": 40, "phase": "HOVER",
                 "position_ned_m": [0, 0, 0]}
        state["time_s"] = 0;session.update(state, 0)
        state["time_s"] = 10;session.update(state, 10)
        state["altitude_m"] = 100;state["time_s"] = 11;session.update(state, 1)
        state["altitude_m"] = 40;state["time_s"] = 12;session.update(state, 1)
        state["time_s"] = 20
        result = session.update(state, 8)
        self.assertFalse(result["progress"]["hold_altitude"])
        self.assertLess(result["hold_s"], 12)

    def test_mission_definitions_use_valid_vehicle_and_scenario(self):
        for vehicle, missions in mission_catalog().items():
            for item in missions:
                mission = find_mission(item["id"])
                self.assertEqual(mission["vehicle"], vehicle)
                self.assertIn(mission["scenario"], {"mission", "orbital", "planetary"})
                self.assertIn(mission["category"], {"INGEGNERIA", "ESPLORAZIONE", "PILOTAGGIO", "SCIENZA"})
                self.assertTrue(mission["campaign"])
                self.assertTrue(mission["briefing"])
                self.assertTrue(mission["objectives"])
                self.assertGreater(mission["reward"]["credits"], 0)

    def test_desktop_game_routes_start_activity_and_return_career(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1], prefix=".career-test-") as folder:
            with patch.object(DesktopRuntime, "_career_file",
                              staticmethod(lambda: Path(folder)/"career.json")):
                runtime = DesktopRuntime()
                catalog = runtime.dispatch("/desktop/game/catalog", {"vehicle": "drone"}, "POST")
                self.assertEqual(len(catalog["drone"]), 3)
                snapshot = runtime.dispatch("/desktop/game/start", {"mission_id": "drone_grid"}, "POST")
                self.assertEqual(snapshot["game"]["mission"]["id"], "drone_grid")
                self.assertEqual(snapshot["desktop"]["play_mode"], "free")
                self.assertEqual(snapshot["state"]["vehicle"], "drone")
                self.assertTrue((Path(folder)/"career.json").exists())

    def test_locked_followup_mission_requires_previous_career_completion(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1], prefix=".career-test-") as folder:
            with patch.object(DesktopRuntime, "_career_file",
                              staticmethod(lambda: Path(folder)/"career.json")):
                runtime = DesktopRuntime()
                with self.assertRaises(ValueError):
                    runtime.dispatch("/desktop/game/start", {"mission_id": "air_alpine"}, "POST")


if __name__ == "__main__":
    unittest.main()
