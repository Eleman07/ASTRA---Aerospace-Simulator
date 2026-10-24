"""Lightweight deterministic navigation filters and guidance helpers."""

from __future__ import annotations

import math
import random

from .constants import OMEGA_EARTH


def _joseph_scalar_position_update(
        covariance: list[list[float]], measurement_variance: float
        ) -> tuple[list[float], list[list[float]], float]:
    """Return a scalar altitude/position gain and Joseph-form covariance.

    Both navigation filters observe only the first state in each 3-state
    axis. The Joseph form is more resistant to roundoff than ``(I-KH)P`` and
    preserves a symmetric positive-semidefinite covariance in exact
    arithmetic.
    """
    innovation_variance = covariance[0][0] + measurement_variance
    gain = [covariance[i][0] / innovation_variance for i in range(3)]
    a = [[(1.0 if i == j else 0.0) - gain[i] * (1.0 if j == 0 else 0.0)
          for j in range(3)] for i in range(3)]
    ap = [[sum(a[i][k] * covariance[k][j] for k in range(3))
           for j in range(3)] for i in range(3)]
    updated = [[sum(ap[i][k] * a[j][k] for k in range(3)) +
                gain[i] * measurement_variance * gain[j]
                for j in range(3)] for i in range(3)]
    for i in range(3):
        updated[i][i] = max(0.0, updated[i][i])
        for j in range(i + 1, 3):
            mean = 0.5 * (updated[i][j] + updated[j][i])
            updated[i][j] = mean
            updated[j][i] = mean
    return gain, updated, innovation_variance


def continuous_lqr_double_integrator_gains(position_weight: float,
                                            velocity_weight: float,
                                            control_weight: float
                                            ) -> tuple[float, float]:
    """Return continuous-time LQR gains for a double-integrator plant.

    The state is position and velocity, control is acceleration, and the
    quadratic cost is ``q_position*x² + q_velocity*v² + r*a²``. The closed-form
    algebraic Riccati solution avoids an iterative solver and guarantees finite,
    positive feedback gains for the validated positive-semidefinite weights.
    """
    weights = (float(position_weight), float(velocity_weight), float(control_weight))
    if (not all(math.isfinite(weight) for weight in weights) or
            weights[0] <= 0.0 or weights[1] < 0.0 or weights[2] <= 0.0):
        raise ValueError("LQR weights require q_position > 0, q_velocity >= 0, r > 0")
    q_position, q_velocity, r = weights
    position_gain = math.sqrt(q_position/r)
    velocity_gain = math.sqrt(q_velocity/r+2.0*position_gain)
    return position_gain, velocity_gain


def lqr_double_integrator_acceleration(
        position_error_m: float, velocity_m_s: float, *,
        position_weight: float = 1.44, velocity_weight: float = 0.0,
        control_weight: float = 1.0,
        max_acceleration_m_s2: float = 3.0) -> float:
    """Compute a saturated LQR acceleration command from position/velocity."""
    error = float(position_error_m)
    velocity = float(velocity_m_s)
    limit = float(max_acceleration_m_s2)
    if not all(math.isfinite(value) for value in (error, velocity, limit)) or limit <= 0.0:
        raise ValueError("LQR state and acceleration limit must be finite; limit must be positive")
    position_gain, velocity_gain = continuous_lqr_double_integrator_gains(
        position_weight, velocity_weight, control_weight)
    command = position_gain*error-velocity_gain*velocity
    return max(-limit, min(limit, command))


UAV_HORIZONTAL_LQR_WEIGHTS = (1.44, 0.0, 1.0)
UAV_VERTICAL_LQR_WEIGHTS = (0.1296, 3.5236, 1.0)


class VerticalNavigationKF:
    """Three-state vertical Kalman filter fusing IMU, barometer and GNSS altitude.

    State: altitude up, vertical velocity up, and vertical accelerometer bias.
    Measurements are generated from truth with fixed biases and repeatable
    disturbances, so a mission can be reproduced exactly across runs.

    Barometer and GNSS-altitude innovations above conservative normalized
    gates are rejected as outliers. If barometer fixes stop, a lower-rate,
    noisier GNSS-altitude measurement continues the solution; if both are
    unavailable, covariance grows under inertial propagation.
    """

    INNOVATION_NIS_GATE = 16.0
    GNSS_ALTITUDE_PERIOD_S = 1.0
    GNSS_ALTITUDE_NOISE_SIGMA_M = 3.0

    def __init__(self) -> None:
        self.reset()

    def reset(self, altitude_m: float = 0.0,
              vertical_speed_m_s: float = 0.0) -> None:
        self.x = [altitude_m, vertical_speed_m_s, 0.0]
        self.P = [[1.0, 0.0, 0.0],
                  [0.0, 2.0, 0.0],
                  [0.0, 0.0, 0.25]]
        self._last_truth_speed = vertical_speed_m_s
        self._last_baro_s = -math.inf
        self._last_gnss_altitude_s = -math.inf
        self._last_valid_baro_s: float | None = None
        self._last_valid_gnss_altitude_s: float | None = None
        self._time_s = 0.0
        self.baro_updates = 0
        self.baro_rejected = 0
        self.baro_dropout_epochs = 0
        self.gnss_altitude_updates = 0
        self.gnss_altitude_rejected = 0
        self.gnss_altitude_dropout_epochs = 0
        self.last_innovation_m = 0.0
        self.last_baro_accepted = True
        self.last_baro_status = "WAITING"
        self.last_gnss_altitude_innovation_m = 0.0
        self.last_gnss_altitude_status = "WAITING"

    def update(self, dt_s: float, truth_altitude_m: float,
               truth_vertical_speed_m_s: float, time_s: float,
               *, barometer_measurement_m: float | None = None,
               barometer_available: bool = True,
               gnss_altitude_measurement_m: float | None = None,
               gnss_altitude_available: bool = True) -> None:
        dt = max(1e-5, min(float(dt_s), 0.25))
        self._time_s = float(time_s)
        true_accel = (truth_vertical_speed_m_s - self._last_truth_speed) / dt
        self._last_truth_speed = truth_vertical_speed_m_s

        # Fixed sensor bias plus deterministic vibration/noise keeps replays stable.
        accel_meas = (true_accel + 0.035 + 0.035 * math.sin(7.1 * time_s)
                      + 0.018 * math.sin(19.7 * time_s))
        h, v, bias = self.x
        corrected_accel = accel_meas - bias
        self.x[0] = h + v * dt + 0.5 * corrected_accel * dt * dt
        self.x[1] = v + corrected_accel * dt

        F = [[1.0, dt, -0.5 * dt * dt],
             [0.0, 1.0, -dt],
             [0.0, 0.0, 1.0]]
        fp = [[sum(F[i][k] * self.P[k][j] for k in range(3))
               for j in range(3)] for i in range(3)]
        p_next = [[sum(fp[i][k] * F[j][k] for k in range(3))
                   for j in range(3)] for i in range(3)]
        accel_var = 0.18 ** 2
        p_next[0][0] += accel_var * dt ** 3 / 3.0
        p_next[0][1] += accel_var * dt ** 2 / 2.0
        p_next[1][0] += accel_var * dt ** 2 / 2.0
        p_next[1][1] += accel_var * dt
        p_next[2][2] += 0.004 ** 2 * dt
        self.P = p_next

        if time_s - self._last_baro_s >= 0.1 - 1e-9:
            self._last_baro_s = time_s
            if not barometer_available:
                self.baro_dropout_epochs += 1
                self.last_baro_accepted = False
                self.last_baro_status = "NO_FIX"
            else:
                baro = (truth_altitude_m + 0.22 + 0.28 * math.sin(0.73 * time_s)
                        + 0.09 * math.sin(2.41 * time_s)
                        if barometer_measurement_m is None else
                        float(barometer_measurement_m))
                if not math.isfinite(baro):
                    raise ValueError("barometer measurement must be finite")
                self.last_baro_accepted, self.last_innovation_m = (
                    self._fuse_altitude_measurement(baro, 0.55**2))
                if self.last_baro_accepted:
                    self._last_valid_baro_s = time_s
                    self.last_baro_status = "VALID"
                    self.baro_updates += 1
                else:
                    self.last_baro_status = "OUTLIER_REJECTED"
                    self.baro_rejected += 1

        if time_s - self._last_gnss_altitude_s >= self.GNSS_ALTITUDE_PERIOD_S - 1e-9:
            self._last_gnss_altitude_s = time_s
            if not gnss_altitude_available:
                self.gnss_altitude_dropout_epochs += 1
                self.last_gnss_altitude_status = "NO_FIX"
            else:
                gnss_altitude = (
                    truth_altitude_m + 1.0 + 1.4*math.sin(0.23*time_s) +
                    0.6*math.sin(0.71*time_s)
                    if gnss_altitude_measurement_m is None else
                    float(gnss_altitude_measurement_m))
                if not math.isfinite(gnss_altitude):
                    raise ValueError("GNSS altitude measurement must be finite")
                accepted, innovation = self._fuse_altitude_measurement(
                    gnss_altitude, self.GNSS_ALTITUDE_NOISE_SIGMA_M**2)
                self.last_gnss_altitude_innovation_m = innovation
                if accepted:
                    self._last_valid_gnss_altitude_s = time_s
                    self.last_gnss_altitude_status = "VALID"
                    self.gnss_altitude_updates += 1
                else:
                    self.last_gnss_altitude_status = "OUTLIER_REJECTED"
                    self.gnss_altitude_rejected += 1

    def _fuse_altitude_measurement(self, measurement_m: float,
                                   measurement_variance_m2: float
                                   ) -> tuple[bool, float]:
        innovation = measurement_m - self.x[0]
        innovation_variance = self.P[0][0] + measurement_variance_m2
        if innovation*innovation/innovation_variance > self.INNOVATION_NIS_GATE:
            return False, innovation
        gain, self.P, _ = _joseph_scalar_position_update(
            self.P, measurement_variance_m2)
        for index in range(3):
            self.x[index] += gain[index] * innovation
        return True, innovation

    def report(self) -> dict[str, float | int | str]:
        barometer_age_s = (None if self._last_valid_baro_s is None else
                           max(0.0, self._time_s-self._last_valid_baro_s))
        gnss_altitude_age_s = (
            None if self._last_valid_gnss_altitude_s is None else
            max(0.0, self._time_s-self._last_valid_gnss_altitude_s))
        barometer_fresh = (self.last_baro_status == "VALID" and
                           barometer_age_s is not None and barometer_age_s <= 0.25)
        gnss_altitude_fresh = (
            self.last_gnss_altitude_status == "VALID" and
            gnss_altitude_age_s is not None and gnss_altitude_age_s <= 2.5)
        active_sources = (["BAROMETER"] if barometer_fresh else [])
        if gnss_altitude_fresh:
            active_sources.append("GNSS_ALTITUDE")
        if not active_sources:
            active_sources.append("IMU_ONLY")
        solution_integrity = (
            "VALID" if barometer_fresh and gnss_altitude_fresh else
            "DEGRADED_BACKUP" if active_sources != ["IMU_ONLY"] else "INS_ONLY")
        return {
            "estimator": "vertical Kalman filter · IMU + barometer + GNSS altitude",
            "altitude_m": self.x[0],
            "vertical_speed_m_s": self.x[1],
            "accelerometer_bias_m_s2": self.x[2],
            "altitude_sigma_m": math.sqrt(max(0.0, self.P[0][0])),
            "barometer_updates": self.baro_updates,
            "barometer_rejected": self.baro_rejected,
            "barometer_dropout_epochs": self.baro_dropout_epochs,
            "barometer_integrity": self.last_baro_status,
            "barometer_age_s": barometer_age_s,
            "last_baro_innovation_m": self.last_innovation_m,
            "gnss_altitude_updates": self.gnss_altitude_updates,
            "gnss_altitude_rejected": self.gnss_altitude_rejected,
            "gnss_altitude_dropout_epochs": self.gnss_altitude_dropout_epochs,
            "gnss_altitude_integrity": self.last_gnss_altitude_status,
            "gnss_altitude_age_s": gnss_altitude_age_s,
            "gnss_altitude_measurement_sigma_m": self.GNSS_ALTITUDE_NOISE_SIGMA_M,
            "last_gnss_altitude_innovation_m": self.last_gnss_altitude_innovation_m,
            "vertical_solution_integrity": solution_integrity,
            "vertical_solution_sources": active_sources,
        }


class HorizontalNavigationKF:
    """Planar IMU + GNSS Kalman filter for a local north/east vehicle state.

    Each axis estimates position, velocity and accelerometer bias. Synthetic
    GNSS position fixes arrive at 5 Hz; the deterministic sensor errors make
    the filter repeatable while retaining a measurable innovation and error.
    A two-axis normalized innovation gate rejects gross fixes; accepted fixes
    use the Joseph covariance update independently on north and east states.
    """

    INNOVATION_NIS_GATE = 20.0

    def __init__(self) -> None:
        self.reset()

    def reset(self, position_ned_m: list[float] | tuple[float, float] = (0.0, 0.0),
              velocity_ned_m_s: list[float] | tuple[float, float] = (0.0, 0.0)) -> None:
        self.x = [[float(position_ned_m[i]), float(velocity_ned_m_s[i]), 0.0]
                  for i in range(2)]
        self.P = [[[2.25, 0.0, 0.0],
                   [0.0, 1.0, 0.0],
                   [0.0, 0.0, 0.16]] for _ in range(2)]
        self._last_truth_velocity = [float(value) for value in velocity_ned_m_s]
        self._last_gnss_s = -math.inf
        self._last_valid_gnss_s: float | None = None
        self._time_s = 0.0
        self.gnss_updates = 0
        self.gnss_rejected = 0
        self.gnss_dropout_epochs = 0
        self.last_gnss_innovation_m = [0.0, 0.0]
        self.last_gnss_accepted = True
        self.last_gnss_status = "WAITING"

    def update(self, dt_s: float,
               truth_position_ned_m: list[float] | tuple[float, float],
               truth_velocity_ned_m_s: list[float] | tuple[float, float],
               time_s: float, *,
               gnss_available: bool = True,
               gnss_position_measurement_ned_m: list[float] | tuple[float, float] | None = None
               ) -> None:
        dt = max(1e-5, min(float(dt_s), 0.25))
        self._time_s = float(time_s)
        for axis in range(2):
            phase = 0.9 * axis
            true_accel = (truth_velocity_ned_m_s[axis] -
                          self._last_truth_velocity[axis]) / dt
            accel_meas = (true_accel + (0.028 if axis == 0 else -0.021) +
                          0.025 * math.sin(6.7 * time_s + phase) +
                          0.012 * math.sin(18.1 * time_s + phase))
            self._last_truth_velocity[axis] = truth_velocity_ned_m_s[axis]

            position, velocity, bias = self.x[axis]
            corrected_accel = accel_meas - bias
            self.x[axis][0] = position + velocity * dt + 0.5 * corrected_accel * dt**2
            self.x[axis][1] = velocity + corrected_accel * dt
            f = [[1.0, dt, -0.5 * dt**2],
                 [0.0, 1.0, -dt],
                 [0.0, 0.0, 1.0]]
            fp = [[sum(f[i][k] * self.P[axis][k][j] for k in range(3))
                   for j in range(3)] for i in range(3)]
            predicted = [[sum(fp[i][k] * f[j][k] for k in range(3))
                          for j in range(3)] for i in range(3)]
            accel_var = 0.20**2
            predicted[0][0] += accel_var * dt**3 / 3.0
            predicted[0][1] += accel_var * dt**2 / 2.0
            predicted[1][0] += accel_var * dt**2 / 2.0
            predicted[1][1] += accel_var * dt
            predicted[2][2] += 0.004**2 * dt
            self.P[axis] = predicted

        if time_s - self._last_gnss_s >= 0.2 - 1e-9:
            self._last_gnss_s = time_s
            if not gnss_available:
                self.gnss_dropout_epochs += 1
                self.last_gnss_accepted = False
                self.last_gnss_status = "NO_FIX"
                return
            if gnss_position_measurement_ned_m is not None and (
                    len(gnss_position_measurement_ned_m) != 2 or
                    not all(math.isfinite(float(value))
                            for value in gnss_position_measurement_ned_m)):
                raise ValueError("GNSS position measurement must contain two finite values")
            innovations: list[float] = []
            normalized_innovations_squared = 0.0
            for axis in range(2):
                phase = 0.8 * axis
                gnss_position = (
                    truth_position_ned_m[axis] +
                    0.35 * math.sin(0.73 * time_s + phase) +
                    0.12 * math.sin(2.41 * time_s + phase)
                    if gnss_position_measurement_ned_m is None else
                    float(gnss_position_measurement_ned_m[axis]))
                innovation = gnss_position - self.x[axis][0]
                variance = self.P[axis][0][0] + 0.8**2
                normalized_innovations_squared += innovation * innovation / variance
                innovations.append(innovation)
            self.last_gnss_innovation_m = innovations
            self.last_gnss_accepted = (
                normalized_innovations_squared <= self.INNOVATION_NIS_GATE)
            if self.last_gnss_accepted:
                for axis, innovation in enumerate(innovations):
                    gain, self.P[axis], _ = _joseph_scalar_position_update(
                        self.P[axis], 0.8**2)
                    for i in range(3):
                        self.x[axis][i] += gain[i] * innovation
                self.gnss_updates += 1
                self._last_valid_gnss_s = time_s
                self.last_gnss_status = "VALID"
            else:
                self.gnss_rejected += 1
                self.last_gnss_status = "OUTLIER_REJECTED"

    @staticmethod
    def _stabilize_covariance(matrix: list[list[float]]) -> None:
        for i in range(3):
            matrix[i][i] = max(0.0, matrix[i][i])
            for j in range(i + 1, 3):
                mean = 0.5 * (matrix[i][j] + matrix[j][i])
                matrix[i][j] = mean
                matrix[j][i] = mean

    def report(self) -> dict[str, float | int | str | list[float]]:
        return {
            "estimator": "horizontal Kalman filter · IMU + GNSS",
            "position_ned_m": [axis[0] for axis in self.x],
            "velocity_ned_m_s": [axis[1] for axis in self.x],
            "accelerometer_bias_ned_m_s2": [axis[2] for axis in self.x],
            "position_sigma_m": [math.sqrt(max(0.0, axis[0][0])) for axis in self.P],
            "gnss_updates": self.gnss_updates,
            "gnss_rejected": self.gnss_rejected,
            "gnss_dropout_epochs": self.gnss_dropout_epochs,
            "gnss_integrity": self.last_gnss_status,
            "gnss_age_s": (None if self._last_valid_gnss_s is None else
                           max(0.0, self._time_s-self._last_valid_gnss_s)),
            "last_gnss_innovation_m": list(self.last_gnss_innovation_m),
        }


class RelativeNavigationKF:
    """RTN relative-state Kalman filter driven by synthetic relative-GNSS fixes.

    The predictor uses the exact circular-reference Clohessy-Wiltshire state
    transition matrix. Position and velocity fixes arrive at 1 Hz, have
    repeatable zero-mean Gaussian errors, and are fused with a Joseph-form
    covariance update. The filter's estimate, rather than truth telemetry, can
    be fed to the rendezvous controller.
    """

    MEASUREMENT_PERIOD_S = 1.0
    POSITION_NOISE_SIGMA_M = 0.5
    VELOCITY_NOISE_SIGMA_M_S = 0.01
    ACCELERATION_NOISE_PSD_M2_S3 = 1.0e-6

    def __init__(self, seed: int = 20261023) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("relative navigation seed must be between 0 and 4294967295")
        self.seed = seed
        self.reset()

    def reset(self, position_rtn_m: list[float] | tuple[float, float, float] =
              (0.0, 0.0, 0.0),
              velocity_rtn_m_s: list[float] | tuple[float, float, float] =
              (0.0, 0.0, 0.0)) -> None:
        if (len(position_rtn_m) != 3 or len(velocity_rtn_m_s) != 3 or
                any(not math.isfinite(float(value))
                    for value in (*position_rtn_m, *velocity_rtn_m_s))):
            raise ValueError("relative navigation initial state must contain six finite values")
        self.rng = random.Random(self.seed)
        prior_sigmas = [2.0, 2.0, 2.0, 0.05, 0.05, 0.05]
        truth = [float(value) for value in position_rtn_m] + [
            float(value) for value in velocity_rtn_m_s]
        self.x = [value+self.rng.gauss(0.0, sigma)
                  for value, sigma in zip(truth, prior_sigmas)]
        self.P = [[0.0 for _ in range(6)] for _ in range(6)]
        for index, variance in enumerate((4.0, 4.0, 4.0, 0.0025, 0.0025, 0.0025)):
            self.P[index][index] = variance
        self.measurement_updates = 0
        self.last_measurement_time_s: float | None = None
        self.next_measurement_time_s = self.MEASUREMENT_PERIOD_S
        self.last_position_innovation_m = [0.0, 0.0, 0.0]
        self.last_velocity_innovation_m_s = [0.0, 0.0, 0.0]

    @staticmethod
    def _transition(mean_motion_rad_s: float, dt_s: float) -> list[list[float]]:
        n = float(mean_motion_rad_s)
        dt = float(dt_s)
        if not math.isfinite(n) or n <= 0.0 or not math.isfinite(dt) or dt < 0.0:
            raise ValueError("CW prediction requires positive mean motion and nonnegative dt")
        if dt == 0.0:
            return [[1.0 if i == j else 0.0 for j in range(6)] for i in range(6)]
        nt = n*dt
        sine, cosine = math.sin(nt), math.cos(nt)
        one_minus_cosine = 1.0-cosine
        return [
            [4.0-3.0*cosine, 0.0, 0.0,
             sine/n, 2.0*one_minus_cosine/n, 0.0],
            [6.0*(sine-nt), 1.0, 0.0,
             -2.0*one_minus_cosine/n, (4.0*sine-3.0*nt)/n, 0.0],
            [0.0, 0.0, cosine, 0.0, 0.0, sine/n],
            [3.0*n*sine, 0.0, 0.0, cosine, 2.0*sine, 0.0],
            [-6.0*n*one_minus_cosine, 0.0, 0.0,
             -2.0*sine, 4.0*cosine-3.0, 0.0],
            [0.0, 0.0, -n*sine, 0.0, 0.0, cosine],
        ]

    @staticmethod
    def _invert(matrix: list[list[float]]) -> list[list[float]]:
        size = len(matrix)
        augmented = [list(row) + [1.0 if i == j else 0.0
                                  for j in range(size)]
                     for i, row in enumerate(matrix)]
        for column in range(size):
            pivot = max(range(column, size),
                        key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-18:
                raise ArithmeticError("relative navigation innovation covariance is singular")
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            augmented[column] = [value/divisor for value in augmented[column]]
            for row in range(size):
                if row == column:
                    continue
                factor = augmented[row][column]
                augmented[row] = [augmented[row][j]-factor*augmented[column][j]
                                  for j in range(2*size)]
        return [row[size:] for row in augmented]

    @staticmethod
    def _symmetrize(matrix: list[list[float]]) -> None:
        for i in range(6):
            matrix[i][i] = max(0.0, matrix[i][i])
            for j in range(i+1, 6):
                mean = 0.5*(matrix[i][j]+matrix[j][i])
                matrix[i][j] = mean
                matrix[j][i] = mean

    def _predict(self, dt_s: float, mean_motion_rad_s: float,
                 control_acceleration_rtn_m_s2: list[float] | tuple[float, ...]) -> None:
        if dt_s <= 0.0:
            return
        transition = self._transition(mean_motion_rad_s, dt_s)
        self.x = [sum(transition[i][j]*self.x[j] for j in range(6))
                  for i in range(6)]
        n, t = mean_motion_rad_s, dt_s
        sine, cosine = math.sin(n*t), math.cos(n*t)
        one_minus_cosine = 1.0-cosine
        radial, transverse, normal = control_acceleration_rtn_m_s2
        control_delta = [
            one_minus_cosine/n**2*radial +
            2.0*(t-sine/n)/n*transverse,
            -2.0*(t-sine/n)/n*radial +
            (4.0*one_minus_cosine/n**2-1.5*t**2)*transverse,
            one_minus_cosine/n**2*normal,
            sine/n*radial + 2.0*one_minus_cosine/n*transverse,
            -2.0*one_minus_cosine/n*radial +
            (4.0*sine/n-3.0*t)*transverse,
            sine/n*normal,
        ]
        self.x = [state+delta for state, delta in zip(self.x, control_delta)]
        fp = [[sum(transition[i][k]*self.P[k][j] for k in range(6))
               for j in range(6)] for i in range(6)]
        self.P = [[sum(fp[i][k]*transition[j][k] for k in range(6))
                   for j in range(6)] for i in range(6)]
        acceleration_psd = self.ACCELERATION_NOISE_PSD_M2_S3
        for axis in range(3):
            position, velocity = axis, axis+3
            self.P[position][position] += acceleration_psd*dt_s**3/3.0
            self.P[position][velocity] += acceleration_psd*dt_s**2/2.0
            self.P[velocity][position] += acceleration_psd*dt_s**2/2.0
            self.P[velocity][velocity] += acceleration_psd*dt_s
        self._symmetrize(self.P)

    def _measurement_update(self, truth_position_rtn_m: list[float] | tuple[float, ...],
                            truth_velocity_rtn_m_s: list[float] | tuple[float, ...],
                            time_s: float) -> None:
        position_sigma = self.POSITION_NOISE_SIGMA_M
        velocity_sigma = self.VELOCITY_NOISE_SIGMA_M_S
        measurement = [float(value)+self.rng.gauss(0.0, position_sigma)
                       for value in truth_position_rtn_m] + [
            float(value)+self.rng.gauss(0.0, velocity_sigma)
            for value in truth_velocity_rtn_m_s]
        innovation = [measurement[i]-self.x[i] for i in range(6)]
        measurement_variances = [position_sigma**2]*3+[velocity_sigma**2]*3
        innovation_covariance = [[self.P[i][j] +
                                  (measurement_variances[i] if i == j else 0.0)
                                  for j in range(6)] for i in range(6)]
        inverse = self._invert(innovation_covariance)
        gain = [[sum(self.P[i][k]*inverse[k][j] for k in range(6))
                 for j in range(6)] for i in range(6)]
        for i in range(6):
            self.x[i] += sum(gain[i][j]*innovation[j] for j in range(6))
        residual_map = [[(1.0 if i == j else 0.0)-gain[i][j]
                         for j in range(6)] for i in range(6)]
        ap = [[sum(residual_map[i][k]*self.P[k][j] for k in range(6))
               for j in range(6)] for i in range(6)]
        posterior = [[sum(ap[i][k]*residual_map[j][k] for k in range(6)) +
                      sum(gain[i][k]*measurement_variances[k]*gain[j][k]
                          for k in range(6))
                      for j in range(6)] for i in range(6)]
        self.P = posterior
        self._symmetrize(self.P)
        self.last_position_innovation_m = innovation[:3]
        self.last_velocity_innovation_m_s = innovation[3:]
        self.last_measurement_time_s = time_s
        self.measurement_updates += 1

    def update(self, dt_s: float,
               truth_position_rtn_m: list[float] | tuple[float, ...],
               truth_velocity_rtn_m_s: list[float] | tuple[float, ...],
               time_s: float, mean_motion_rad_s: float,
               control_acceleration_rtn_m_s2: list[float] | tuple[float, ...] =
               (0.0, 0.0, 0.0),
               previous_truth_position_rtn_m: list[float] | tuple[float, ...] | None = None,
               previous_truth_velocity_rtn_m_s: list[float] | tuple[float, ...] | None = None) -> None:
        current_position = tuple(float(value) for value in truth_position_rtn_m)
        current_velocity = tuple(float(value) for value in truth_velocity_rtn_m_s)
        previous_position = tuple(float(value) for value in (
            truth_position_rtn_m if previous_truth_position_rtn_m is None
            else previous_truth_position_rtn_m))
        previous_velocity = tuple(float(value) for value in (
            truth_velocity_rtn_m_s if previous_truth_velocity_rtn_m_s is None
            else previous_truth_velocity_rtn_m_s))
        values = (dt_s, time_s, mean_motion_rad_s,
                  *current_position, *current_velocity,
                  *previous_position, *previous_velocity,
                  *control_acceleration_rtn_m_s2)
        if (len(current_position) != 3 or len(current_velocity) != 3 or
                len(previous_position) != 3 or len(previous_velocity) != 3 or
                len(control_acceleration_rtn_m_s2) != 3 or
                any(not math.isfinite(float(value)) for value in values) or
                dt_s < 0.0 or time_s < 0.0 or time_s+1e-9 < dt_s):
            raise ValueError("relative navigation update requires finite RTN state and time")
        dt = float(dt_s)
        end_time = float(time_s)
        start_time = end_time-dt
        mean_motion = float(mean_motion_rad_s)
        control = tuple(float(value) for value in control_acceleration_rtn_m_s2)
        elapsed = 0.0
        while time_s+1e-9 >= self.next_measurement_time_s:
            sample_offset = min(dt, max(elapsed,
                                        self.next_measurement_time_s-start_time))
            self._predict(sample_offset-elapsed, mean_motion, control)
            fraction = sample_offset/dt if dt > 0.0 else 1.0
            sample_position = [previous_position[i] + fraction*(current_position[i]-previous_position[i])
                               for i in range(3)]
            sample_velocity = [previous_velocity[i] + fraction*(current_velocity[i]-previous_velocity[i])
                               for i in range(3)]
            self._measurement_update(sample_position, sample_velocity,
                                     self.next_measurement_time_s)
            elapsed = sample_offset
            self.next_measurement_time_s += self.MEASUREMENT_PERIOD_S
        self._predict(max(0.0, dt-elapsed), mean_motion, control)

    def report(self) -> dict[str, float | int | str | list[float]]:
        return {
            "estimator": "relative Kalman filter · CW predictor + noisy relative GNSS",
            "frame": "RTN",
            "position_rtn_m": list(self.x[:3]),
            "velocity_rtn_m_s": list(self.x[3:]),
            "position_sigma_rtn_m": [math.sqrt(max(0.0, self.P[i][i]))
                                     for i in range(3)],
            "velocity_sigma_rtn_m_s": [math.sqrt(max(0.0, self.P[i+3][i+3]))
                                       for i in range(3)],
            "measurement_model": "SYNTHETIC_RELATIVE_GNSS_POSITION_AND_VELOCITY",
            "measurement_epoch_interpolation": "LINEAR_RTN_BETWEEN_PHYSICS_STEPS",
            "initialization_model": "GAUSSIAN_PRIOR_2M_POSITION_0.05M_S_VELOCITY",
            "measurement_period_s": self.MEASUREMENT_PERIOD_S,
            "position_noise_sigma_m": self.POSITION_NOISE_SIGMA_M,
            "velocity_noise_sigma_m_s": self.VELOCITY_NOISE_SIGMA_M_S,
            "measurement_updates": self.measurement_updates,
            "last_measurement_time_s": self.last_measurement_time_s,
            "last_position_innovation_m": list(self.last_position_innovation_m),
            "last_velocity_innovation_m_s": list(self.last_velocity_innovation_m_s),
            "seed": self.seed,
        }


class SpaceNavigationKF:
    """ECI strapdown INS corrected by synthetic GNSS position/velocity fixes.

    The nominal state is inertial position and velocity. Specific force is
    rotated from body to ECI with the simulated attitude reference and added
    to the J2 gravity model. GNSS fixes are generated at 1 Hz with explicit
    noise, a six-dimensional innovation gate, and Joseph covariance updates.
    Attitude-reference error and lever-arm effects are intentionally outside
    this translational filter and are identified in its report.
    """

    GNSS_PERIOD_S = 1.0
    IMU_PERIOD_S = 0.05
    GNSS_POSITION_SIGMA_M = 3.0
    GNSS_VELOCITY_SIGMA_M_S = 0.15
    ACCELEROMETER_NOISE_SIGMA_M_S2 = 0.02
    ACCELEROMETER_BIAS_SIGMA_M_S2 = 0.001
    GNSS_NIS_GATE = 22.46

    def __init__(self, seed: int = 20261024) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("space navigation seed must be between 0 and 4294967295")
        self.seed = seed
        self.reset()

    def reset(self, position_eci_m: list[float] | tuple[float, float, float] =
              (0.0, 0.0, 0.0),
              velocity_eci_m_s: list[float] | tuple[float, float, float] =
              (0.0, 0.0, 0.0)) -> None:
        if (len(position_eci_m) != 3 or len(velocity_eci_m_s) != 3 or
                any(not math.isfinite(float(value))
                    for value in (*position_eci_m, *velocity_eci_m_s))):
            raise ValueError("space navigation initial state must contain six finite values")
        self.rng = random.Random(self.seed)
        self.x = [float(value) for value in position_eci_m] + [
            float(value) for value in velocity_eci_m_s]
        self.P = [[0.0 for _ in range(6)] for _ in range(6)]
        for i, variance in enumerate((9.0, 9.0, 9.0, 0.04, 0.04, 0.04)):
            self.P[i][i] = variance
        self.accelerometer_bias_body_m_s2 = [
            self.rng.gauss(0.0, self.ACCELEROMETER_BIAS_SIGMA_M_S2)
            for _ in range(3)]
        self._time_s = 0.0
        self.next_gnss_time_s = self.GNSS_PERIOD_S
        self.last_gnss_time_s: float | None = None
        self.last_gnss_attempt_time_s: float | None = None
        self.gnss_updates = 0
        self.gnss_rejected = 0
        self.gnss_dropout_epochs = 0
        self.last_gnss_status = "WAITING"
        self.last_gnss_nis: float | None = None
        self.last_position_innovation_m = [0.0, 0.0, 0.0]
        self.last_velocity_innovation_m_s = [0.0, 0.0, 0.0]
        self.accelerometer_samples = 0
        self._accelerometer_noise_bucket: int | None = None
        self._accelerometer_noise_body_m_s2 = [0.0, 0.0, 0.0]
        self._last_truth_position = list(position_eci_m)
        self._last_truth_velocity = list(velocity_eci_m_s)

    @staticmethod
    def _body_vector_to_eci(quaternion_body_to_eci: list[float] | tuple[float, ...],
                            vector_body: list[float] | tuple[float, ...]
                            ) -> list[float]:
        if len(quaternion_body_to_eci) != 4 or len(vector_body) != 3:
            raise ValueError("attitude quaternion and accelerometer vector have invalid dimensions")
        q = [float(value) for value in quaternion_body_to_eci]
        vector = [float(value) for value in vector_body]
        if any(not math.isfinite(value) for value in (*q, *vector)):
            raise ValueError("attitude quaternion and accelerometer vector must be finite")
        norm = math.sqrt(sum(value*value for value in q))
        if norm <= 1e-15:
            raise ValueError("attitude quaternion must have nonzero norm")
        w, x, y, z = [value/norm for value in q]
        # q * [0,v] * conjugate(q), expanded to avoid temporary quaternions.
        vx, vy, vz = vector
        tx = 2.0*(y*vz-z*vy)
        ty = 2.0*(z*vx-x*vz)
        tz = 2.0*(x*vy-y*vx)
        return [vx+w*tx+(y*tz-z*ty),
                vy+w*ty+(z*tx-x*tz),
                vz+w*tz+(x*ty-y*tx)]

    @staticmethod
    def _eci_to_ecef(position_eci_m: list[float] | tuple[float, ...],
                     velocity_eci_m_s: list[float] | tuple[float, ...],
                     time_s: float) -> tuple[list[float], list[float]]:
        """Transform an inertial state into an Earth-fixed rotating frame."""
        theta = OMEGA_EARTH*float(time_s)
        cosine, sine = math.cos(theta), math.sin(theta)
        x, y, z = position_eci_m
        vx, vy, vz = velocity_eci_m_s
        # v_ECEF = Rz(-theta) * (v_ECI - omega_Earth x r_ECI).
        rotating_velocity = [vx+OMEGA_EARTH*y,
                             vy-OMEGA_EARTH*x, vz]
        return ([cosine*x+sine*y, -sine*x+cosine*y, z],
                [cosine*rotating_velocity[0]+sine*rotating_velocity[1],
                 -sine*rotating_velocity[0]+cosine*rotating_velocity[1],
                 rotating_velocity[2]])

    @staticmethod
    def _ecef_to_eci(position_ecef_m: list[float] | tuple[float, ...],
                     velocity_ecef_m_s: list[float] | tuple[float, ...],
                     time_s: float) -> tuple[list[float], list[float]]:
        """Transform an Earth-fixed GNSS state into the inertial frame."""
        theta = OMEGA_EARTH*float(time_s)
        cosine, sine = math.cos(theta), math.sin(theta)
        x, y, z = position_ecef_m
        vx, vy, vz = velocity_ecef_m_s
        position = [cosine*x-sine*y, sine*x+cosine*y, z]
        rotating_velocity = [cosine*vx-sine*vy,
                             sine*vx+cosine*vy, vz]
        velocity = [rotating_velocity[0]-OMEGA_EARTH*position[1],
                    rotating_velocity[1]+OMEGA_EARTH*position[0],
                    rotating_velocity[2]]
        return position, velocity

    @staticmethod
    def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
        return [[sum(a[i][k]*b[k][j] for k in range(len(b)))
                 for j in range(len(b[0]))] for i in range(len(a))]

    @staticmethod
    def _transpose(matrix: list[list[float]]) -> list[list[float]]:
        return [list(column) for column in zip(*matrix)]

    @staticmethod
    def _gravity_gradient(position_m: list[float], gravity_fn) -> list[list[float]]:
        gradient = [[0.0 for _ in range(3)] for _ in range(3)]
        for column in range(3):
            delta = max(0.5, abs(position_m[column])*1e-7)
            plus, minus = position_m[:], position_m[:]
            plus[column] += delta
            minus[column] -= delta
            g_plus, g_minus = gravity_fn(plus), gravity_fn(minus)
            for row in range(3):
                gradient[row][column] = (g_plus[row]-g_minus[row])/(2.0*delta)
        return gradient

    def _predict(self, dt_s: float, specific_force_eci_m_s2: list[float],
                 gravity_fn) -> None:
        if dt_s <= 0.0:
            return
        dt = float(dt_s)
        gravity = gravity_fn(self.x[:3])
        gravity_gradient = self._gravity_gradient(self.x[:3], gravity_fn)
        acceleration = [specific_force_eci_m_s2[i]+gravity[i]
                        for i in range(3)]
        self.x[:3] = [self.x[i]+self.x[i+3]*dt+0.5*acceleration[i]*dt*dt
                      for i in range(3)]
        self.x[3:] = [self.x[i+3]+acceleration[i]*dt for i in range(3)]

        transition = [[0.0 for _ in range(6)] for _ in range(6)]
        for i in range(3):
            for j in range(3):
                transition[i][j] = (1.0+0.5*gravity_gradient[i][j]*dt*dt
                                    if i == j else
                                    0.5*gravity_gradient[i][j]*dt*dt)
                transition[i][j+3] = dt if i == j else 0.0
                transition[i+3][j] = gravity_gradient[i][j]*dt
                transition[i+3][j+3] = 1.0 if i == j else 0.0
        fp = self._matmul(transition, self.P)
        self.P = self._matmul(fp, self._transpose(transition))
        # Continuous white acceleration noise, including integrated position
        # and position/velocity cross-covariance terms.
        q = self.ACCELEROMETER_NOISE_SIGMA_M_S2**2
        for axis in range(3):
            position, velocity = axis, axis+3
            self.P[position][position] += q*dt**3/3.0
            self.P[position][velocity] += q*dt**2/2.0
            self.P[velocity][position] += q*dt**2/2.0
            self.P[velocity][velocity] += q*dt
        self._symmetrize(self.P)

    @staticmethod
    def _symmetrize(covariance: list[list[float]]) -> None:
        for i in range(6):
            covariance[i][i] = max(0.0, covariance[i][i])
            for j in range(i+1, 6):
                mean = 0.5*(covariance[i][j]+covariance[j][i])
                covariance[i][j] = mean
                covariance[j][i] = mean

    def _gnss_update(self, position_eci_m: list[float],
                     velocity_eci_m_s: list[float], time_s: float) -> None:
        position_sigma = self.GNSS_POSITION_SIGMA_M
        velocity_sigma = self.GNSS_VELOCITY_SIGMA_M_S
        position_ecef, velocity_ecef = self._eci_to_ecef(
            position_eci_m, velocity_eci_m_s, time_s)
        measured_position_ecef = [value+self.rng.gauss(0.0, position_sigma)
                                  for value in position_ecef]
        measured_velocity_ecef = [value+self.rng.gauss(0.0, velocity_sigma)
                                  for value in velocity_ecef]
        measured_position_eci, measured_velocity_eci = self._ecef_to_eci(
            measured_position_ecef, measured_velocity_ecef, time_s)
        measurement = measured_position_eci+measured_velocity_eci
        innovation = [measurement[i]-self.x[i] for i in range(6)]
        variances = [position_sigma**2]*3+[velocity_sigma**2]*3
        innovation_covariance = [[self.P[i][j]+(variances[i] if i == j else 0.0)
                                  for j in range(6)] for i in range(6)]
        inverse = RelativeNavigationKF._invert(innovation_covariance)
        nis = sum(innovation[i]*inverse[i][j]*innovation[j]
                  for i in range(6) for j in range(6))
        self.last_gnss_nis = max(0.0, nis)
        self.last_position_innovation_m = innovation[:3]
        self.last_velocity_innovation_m_s = innovation[3:]
        self.last_gnss_attempt_time_s = time_s
        if nis > self.GNSS_NIS_GATE:
            self.gnss_rejected += 1
            self.last_gnss_status = "OUTLIER_REJECTED"
            return
        gain = self._matmul(self.P, inverse)
        self.x = [self.x[i]+sum(gain[i][j]*innovation[j] for j in range(6))
                  for i in range(6)]
        residual = [[(1.0 if i == j else 0.0)-gain[i][j]
                     for j in range(6)] for i in range(6)]
        ap = self._matmul(residual, self.P)
        posterior = self._matmul(ap, self._transpose(residual))
        for i in range(6):
            for j in range(6):
                posterior[i][j] += sum(gain[i][k]*variances[k]*gain[j][k]
                                       for k in range(6))
        self.P = posterior
        self._symmetrize(self.P)
        self.last_gnss_time_s = time_s
        self.gnss_updates += 1
        self.last_gnss_status = "VALID"

    def _accelerometer_noise(self, time_s: float) -> list[float]:
        """Hold each seeded IMU noise sample for one fixed 20 Hz sensor epoch."""
        bucket = max(1, int(math.ceil(time_s/self.IMU_PERIOD_S-1e-10)))
        if bucket != self._accelerometer_noise_bucket:
            sample_rng = random.Random(
                (self.seed+bucket*1_664_525+1_013_904_223) & 0xFFFFFFFF)
            self._accelerometer_noise_body_m_s2 = [
                sample_rng.gauss(0.0, self.ACCELEROMETER_NOISE_SIGMA_M_S2)
                for _ in range(3)]
            self._accelerometer_noise_bucket = bucket
            self.accelerometer_samples += 1
        return self._accelerometer_noise_body_m_s2[:]

    def update(self, dt_s: float,
               specific_force_body_m_s2: list[float] | tuple[float, ...],
               attitude_quaternion_body_to_eci: list[float] | tuple[float, ...],
               truth_position_eci_m: list[float] | tuple[float, ...],
               truth_velocity_eci_m_s: list[float] | tuple[float, ...],
               time_s: float, gravity_fn, *, gnss_available: bool = True,
               previous_truth_position_eci_m: list[float] | tuple[float, ...] | None = None,
               previous_truth_velocity_eci_m_s: list[float] | tuple[float, ...] | None = None
               ) -> None:
        dt = float(dt_s)
        end_time = float(time_s)
        current_position = tuple(float(value) for value in truth_position_eci_m)
        current_velocity = tuple(float(value) for value in truth_velocity_eci_m_s)
        previous_position = tuple(float(value) for value in (
            truth_position_eci_m if previous_truth_position_eci_m is None
            else previous_truth_position_eci_m))
        previous_velocity = tuple(float(value) for value in (
            truth_velocity_eci_m_s if previous_truth_velocity_eci_m_s is None
            else previous_truth_velocity_eci_m_s))
        force_body = tuple(float(value) for value in specific_force_body_m_s2)
        values = (dt, end_time, *current_position, *current_velocity,
                  *previous_position, *previous_velocity, *force_body,
                  *attitude_quaternion_body_to_eci)
        if (dt < 0.0 or end_time < 0.0 or end_time+1e-9 < dt or
                len(current_position) != 3 or len(current_velocity) != 3 or
                len(previous_position) != 3 or len(previous_velocity) != 3 or
                len(force_body) != 3 or
                any(not math.isfinite(value) for value in values)):
            raise ValueError("space navigation update requires finite ECI, IMU, attitude and time inputs")
        if not callable(gravity_fn):
            raise ValueError("space navigation requires a gravity acceleration model")
        accel_noise = self._accelerometer_noise(end_time)
        measured_force_body = [force_body[i]+self.accelerometer_bias_body_m_s2[i]+
                               accel_noise[i] for i in range(3)]
        specific_force_eci = self._body_vector_to_eci(
            attitude_quaternion_body_to_eci, measured_force_body)
        start_time = end_time-dt
        elapsed = 0.0
        while self.next_gnss_time_s <= end_time+1e-9:
            offset = min(dt, max(elapsed, self.next_gnss_time_s-start_time))
            self._predict(offset-elapsed, specific_force_eci, gravity_fn)
            if gnss_available:
                fraction = offset/dt if dt > 0.0 else 1.0
                position = [previous_position[i]+fraction*(current_position[i]-previous_position[i])
                            for i in range(3)]
                velocity = [previous_velocity[i]+fraction*(current_velocity[i]-previous_velocity[i])
                            for i in range(3)]
                self._gnss_update(position, velocity, self.next_gnss_time_s)
            else:
                self.gnss_dropout_epochs += 1
                self.last_gnss_status = "DROPOUT"
            elapsed = offset
            self.next_gnss_time_s += self.GNSS_PERIOD_S
        self._predict(max(0.0, dt-elapsed), specific_force_eci, gravity_fn)
        self._time_s = end_time
        self._last_truth_position = list(current_position)
        self._last_truth_velocity = list(current_velocity)

    def report(self) -> dict[str, object]:
        return {
            "estimator": "ECI strapdown INS · J2 gravity · extended Kalman filter",
            "frame": "ECI",
            "position_eci_m": list(self.x[:3]),
            "velocity_eci_m_s": list(self.x[3:]),
            "position_sigma_eci_m": [math.sqrt(max(0.0, self.P[i][i]))
                                     for i in range(3)],
            "velocity_sigma_eci_m_s": [math.sqrt(max(0.0, self.P[i+3][i+3]))
                                       for i in range(3)],
            "accelerometer_model": "BODY_SPECIFIC_FORCE_WITH_DETERMINISTIC_BIAS_AND_NOISE",
            "attitude_reference": "SIMULATED_QUATERNION_IDEAL_REFERENCE",
            "gravity_model": "EARTH_CENTRAL_PLUS_J2",
            "gnss_model": "SYNTHETIC_ECEF_FIX_TRANSFORMED_TO_ECI",
            "gnss_frame_conversion": "EARTH_ROTATION_Z_AXIS · CONSTANT_SIDEREAL_RATE",
            "earth_rotation_rad_s": OMEGA_EARTH,
            "gnss_period_s": self.GNSS_PERIOD_S,
            "gnss_position_noise_sigma_m": self.GNSS_POSITION_SIGMA_M,
            "gnss_velocity_noise_sigma_m_s": self.GNSS_VELOCITY_SIGMA_M_S,
            "gnss_integrity": self.last_gnss_status,
            "gnss_age_s": (None if self.last_gnss_time_s is None else
                           max(0.0, self._time_s-self.last_gnss_time_s)),
            "last_gnss_attempt_time_s": self.last_gnss_attempt_time_s,
            "gnss_updates": self.gnss_updates,
            "gnss_rejected": self.gnss_rejected,
            "gnss_dropout_epochs": self.gnss_dropout_epochs,
            "last_gnss_nis": self.last_gnss_nis,
            "innovation_gate_nis": self.GNSS_NIS_GATE,
            "last_position_innovation_m": list(self.last_position_innovation_m),
            "last_velocity_innovation_m_s": list(self.last_velocity_innovation_m_s),
            "accelerometer_samples": self.accelerometer_samples,
            "accelerometer_sample_period_s": self.IMU_PERIOD_S,
            "seed": self.seed,
        }


# Preserve the earlier import name for controllers and notebooks that used it.
VerticalNavigationEKF = VerticalNavigationKF
HorizontalNavigationEKF = HorizontalNavigationKF
