"""Regression tests for manual orbital attitude and the SAS command surface."""
from __future__ import annotations

import math
import unittest

from astra.attitude import _q_rotate
from astra.engine import SimulationEngine
from desktop_runtime import DesktopRuntime


def quaternion_distance_deg(a, b):
    dot = abs(sum(x*y for x, y in zip(a, b)))
    return math.degrees(2*math.acos(max(-1.0, min(1.0, dot))))


class OrbitalSASTests(unittest.TestCase):
    def setUp(self):
        self.engine = SimulationEngine()
        self.engine.reset("space", "orbital", advanced_models=True)

    def test_manual_mode_releases_lvlh_servo_and_keeps_inertial_attitude(self):
        initial = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual"})
        self.assertEqual(self.engine.command["attitude_sas_mode"], "manual")
        state = self.engine.step(8.0)
        final = state["attitude_quaternion_body_to_eci"]
        self.assertLess(quaternion_distance_deg(initial, final), .02)
        self.assertEqual(state["attitude_control"]["mode"], "manual")

    def test_manual_torque_rotates_then_zero_torque_does_not_retarget_vertical(self):
        initial = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual",
                                 "attitude_torque_body_fraction": [0, 0, 1]})
        rotated = self.engine.step(12.0)["attitude_quaternion_body_to_eci"]
        self.assertGreater(quaternion_distance_deg(initial, rotated), 2.0)
        rates = self.engine.state()["body_rates_rad_s"]
        self.engine.set_command({"attitude_torque_body_fraction": [0, 0, 0]})
        state = self.engine.step(2.0)
        self.assertGreater(quaternion_distance_deg(rotated,
                            state["attitude_quaternion_body_to_eci"]), .01)
        self.assertGreater(math.sqrt(sum(v*v for v in state["body_rates_rad_s"])), 0.0)
        self.assertGreater(math.sqrt(sum(v*v for v in rates)), 0.0)

    def test_stability_and_orbit_direction_sas_targets(self):
        current = self.engine.state()["attitude_quaternion_body_to_eci"]
        self.engine.set_command({"mode": "manual", "attitude_sas_mode": "stability_assist"})
        stable = self.engine.step(8.0)
        self.assertLess(quaternion_distance_deg(current,
                         stable["attitude_quaternion_body_to_eci"]), .1)
        self.engine.set_command({"attitude_sas_mode": "prograde"})
        prograde = self.engine.step(.2)
        q = prograde["attitude_quaternion_body_to_eci"]
        body_x = _q_rotate(q, [1, 0, 0])
        velocity = prograde["velocity_eci_m_s"]
        vnorm = math.sqrt(sum(v*v for v in velocity))
        self.assertGreater(sum(body_x[i]*velocity[i]/vnorm for i in range(3)), .99)
        self.engine.set_command({"attitude_sas_mode": "target"})
        self.engine.step(.2)
        self.engine.set_command({"attitude_sas_mode": "maneuver_node",
                                 "maneuver_direction_eci": [1, 1, 0]})
        self.engine.step(.2)

    def test_invalid_manual_torque_and_unset_maneuver_are_rejected(self):
        self.engine.set_command({"mode": "manual"})
        with self.assertRaises(ValueError):
            self.engine.set_command({"attitude_torque_body_fraction": [0, 2, 0]})
        with self.assertRaises(ValueError):
            self.engine.set_command({"attitude_sas_mode": "maneuver_node"})

    def test_desktop_gioca_orbit_uses_same_manual_attitude_physics(self):
        runtime = DesktopRuntime()
        snapshot = runtime.dispatch("/desktop/free", {"vehicle": "space",
            "scenario": "orbital", "advanced_models": True}, "POST")
        self.assertEqual(snapshot["desktop"]["play_mode"], "free")
        self.assertEqual(snapshot["state"]["command"]["attitude_sas_mode"], "manual")
        initial = snapshot["state"]["attitude_quaternion_body_to_eci"]
        runtime.dispatch("/command", {"attitude_torque_body_fraction": [1, 0, 0]}, "POST")
        rotated = runtime.engine.step(12.0)["attitude_quaternion_body_to_eci"]
        self.assertGreater(quaternion_distance_deg(initial, rotated), 2.0)


if __name__ == "__main__":
    unittest.main()
