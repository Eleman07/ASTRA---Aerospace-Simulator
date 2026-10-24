"""Control allocation and first-order motor maps for multirotor vehicles."""

from __future__ import annotations

import math
from typing import Sequence


def rotor_geometry(count: int, arm_m: float,
                   yaw_moment_coefficient_m: float) -> list[dict[str, float]]:
    """Return equally spaced rotor positions and alternating spin directions."""
    if (isinstance(count, bool) or not isinstance(count, int) or
            count < 4 or count % 2):
        raise ValueError("a multirotor requires an even number of at least four rotors")
    if (not math.isfinite(arm_m) or arm_m <= 0.0 or
            not math.isfinite(yaw_moment_coefficient_m) or
            yaw_moment_coefficient_m <= 0.0):
        raise ValueError("rotor arm and yaw moment coefficient must be positive and finite")
    phase = math.pi / count if count == 4 else 0.0
    return [{"x_m": arm_m*math.cos(phase+2.0*math.pi*i/count),
             "y_m": arm_m*math.sin(phase+2.0*math.pi*i/count),
             "spin_direction": 1.0 if i % 2 == 0 else -1.0,
             "yaw_moment_coefficient_m": yaw_moment_coefficient_m}
            for i in range(count)]


def rotor_mixer(geometry: Sequence[dict[str, float]]) -> list[list[float]]:
    """Build the minimum-norm rotor-force allocator for [T, Mx, My, Mz]."""
    if len(geometry) < 4:
        raise ValueError("at least four rotors are required to control four wrench axes")
    effectiveness = [[1.0 for _ in geometry],
                     [-rotor["y_m"] for rotor in geometry],
                     [rotor["x_m"] for rotor in geometry],
                     [rotor["spin_direction"] * rotor["yaw_moment_coefficient_m"]
                      for rotor in geometry]]
    gram = [[sum(effectiveness[row][i]*effectiveness[column][i]
                 for i in range(len(geometry)))
             for column in range(4)] for row in range(4)]
    inverse = _invert(gram)
    return [[sum(effectiveness[k][rotor]*inverse[k][axis] for k in range(4))
             for axis in range(4)] for rotor in range(len(geometry))]


def rotor_mixer_with_health(geometry: Sequence[dict[str, float]],
                            health: Sequence[float]
                            ) -> list[list[float]]:
    """Build a minimum-norm allocator that accounts for degraded rotor thrust.

    Health scales the physical thrust produced for a commanded rotor force.
    The allocator inverts the four-axis effectiveness matrix after applying
    those scale factors, so it compensates partial losses while retaining the
    nominal maximum command for each motor.  A rank-deficient configuration
    (for example, a completely failed motor on a quadrotor) is rejected rather
    than returning an unstable allocation.
    """
    if len(geometry) != len(health) or len(geometry) < 4:
        raise ValueError("rotor geometry and health must match and contain at least four rotors")
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0
               for value in health):
        raise ValueError("rotor health values must be finite and within [0, 1]")
    effectiveness = [[health[i] for i in range(len(geometry))],
                     [-geometry[i]["y_m"]*health[i]
                      for i in range(len(geometry))],
                     [geometry[i]["x_m"]*health[i]
                      for i in range(len(geometry))],
                     [geometry[i]["spin_direction"] *
                      geometry[i]["yaw_moment_coefficient_m"]*health[i]
                      for i in range(len(geometry))]]
    gram = [[sum(effectiveness[row][i]*effectiveness[column][i]
                 for i in range(len(geometry)))
             for column in range(4)] for row in range(4)]
    inverse = _invert(gram)
    return [[sum(effectiveness[k][rotor]*inverse[k][axis] for k in range(4))
             for axis in range(4)] for rotor in range(len(geometry))]


def allocate_rotor_thrusts(wrench_N_Nm: Sequence[float],
                           mixer: Sequence[Sequence[float]],
                           max_thrust_per_rotor_N: float) -> list[float]:
    """Allocate a requested wrench and saturate each motor at its physical limits."""
    if len(wrench_N_Nm) != 4 or not all(math.isfinite(value) for value in wrench_N_Nm):
        raise ValueError("rotor wrench must contain four finite values")
    if not math.isfinite(max_thrust_per_rotor_N) or max_thrust_per_rotor_N <= 0.0:
        raise ValueError("maximum rotor thrust must be positive and finite")
    return [max(0.0, min(max_thrust_per_rotor_N,
                         sum(row[axis]*wrench_N_Nm[axis] for axis in range(4))))
            for row in mixer]


def rotor_wrench(thrusts_N: Sequence[float],
                 geometry: Sequence[dict[str, float]]) -> list[float]:
    """Calculate total thrust and body moments from individual rotor forces."""
    if len(thrusts_N) != len(geometry):
        raise ValueError("rotor thrust and geometry arrays must have equal lengths")
    if not all(math.isfinite(value) and value >= 0.0 for value in thrusts_N):
        raise ValueError("rotor thrusts must be finite and nonnegative")
    total = sum(thrusts_N)
    roll = sum(-rotor["y_m"]*thrust for rotor, thrust in zip(geometry, thrusts_N))
    pitch = sum(rotor["x_m"]*thrust for rotor, thrust in zip(geometry, thrusts_N))
    yaw = sum(rotor["spin_direction"]*rotor["yaw_moment_coefficient_m"]*thrust
              for rotor, thrust in zip(geometry, thrusts_N))
    return [total, roll, pitch, yaw]


def thrust_to_motor_speed(thrust_N: float, max_thrust_N: float,
                          max_speed_rad_s: float) -> float:
    """Use the low-order propeller relation T proportional to angular speed squared."""
    if not all(math.isfinite(value) for value in
               (thrust_N, max_thrust_N, max_speed_rad_s)):
        raise ValueError("motor-map values must be finite")
    if max_thrust_N <= 0.0 or max_speed_rad_s <= 0.0:
        raise ValueError("motor-map limits must be positive")
    fraction = max(0.0, min(1.0, thrust_N/max_thrust_N))
    return max_speed_rad_s*math.sqrt(fraction)


def motor_speed_to_thrust(speed_rad_s: float, max_speed_rad_s: float,
                          max_thrust_N: float) -> float:
    """Return bounded rotor thrust from its current angular speed."""
    if not all(math.isfinite(value) for value in
               (speed_rad_s, max_speed_rad_s, max_thrust_N)):
        raise ValueError("motor-map values must be finite")
    if max_speed_rad_s <= 0.0 or max_thrust_N <= 0.0:
        raise ValueError("motor-map limits must be positive")
    fraction = max(0.0, min(1.0, speed_rad_s/max_speed_rad_s))
    return max_thrust_N*fraction*fraction


def _invert(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Invert a small nonsingular square matrix with pivoted elimination."""
    size = len(matrix)
    augmented = [list(row)+[1.0 if i == j else 0.0 for j in range(size)]
                 for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-14:
            raise ValueError("rotor geometry cannot independently control all four axes")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value/scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            scale = augmented[row][column]
            augmented[row] = [value-scale*pivot_value
                              for value, pivot_value in
                              zip(augmented[row], augmented[column])]
    return [row[size:] for row in augmented]
