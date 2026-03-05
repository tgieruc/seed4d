"""Mock carla module for testing pose.py and sensor.py without the real CARLA simulator."""

import math


class Location:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def distance(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)


class Rotation:
    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch = float(pitch)
        self.yaw = float(yaw)
        self.roll = float(roll)


class Transform:
    """Mock CARLA Transform with get_matrix() implementing the real Unreal Engine
    rotation convention: Rz(yaw) * Ry(pitch) * Rx(roll), angles in degrees."""

    def __init__(self, location=None, rotation=None):
        self.location = location if location is not None else Location()
        self.rotation = rotation if rotation is not None else Rotation()

    def get_matrix(self):
        """Return 4x4 transformation matrix matching real CARLA's convention."""
        yaw = math.radians(self.rotation.yaw)
        pitch = math.radians(self.rotation.pitch)
        roll = math.radians(self.rotation.roll)

        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cr, sr = math.cos(roll), math.sin(roll)

        # Rz(yaw) * Ry(pitch) * Rx(roll) — Unreal Engine convention
        m = [
            [
                cy * cp,
                cy * sp * sr - sy * cr,
                cy * sp * cr + sy * sr,
                self.location.x,
            ],
            [
                sy * cp,
                sy * sp * sr + cy * cr,
                sy * sp * cr - cy * sr,
                self.location.y,
            ],
            [
                -sp,
                cp * sr,
                cp * cr,
                self.location.z,
            ],
            [0.0, 0.0, 0.0, 1.0],
        ]
        return m


# Stub types used as type annotations in sensor.py
class World:
    pass


class BlueprintLibrary:
    pass


class Vehicle:
    pass


class WeatherParameters:
    ClearNoon = "ClearNoon"
    CloudyNoon = "CloudyNoon"
    WetNoon = "WetNoon"
    WetCloudyNoon = "WetCloudyNoon"
    MidRainyNoon = "MidRainyNoon"
    HardRainNoon = "HardRainNoon"
    SoftRainNoon = "SoftRainNoon"
    ClearSunset = "ClearSunset"
    CloudySunset = "CloudySunset"
    WetSunset = "WetSunset"
    WetCloudySunset = "WetCloudySunset"
    MidRainSunset = "MidRainSunset"
    HardRainSunset = "HardRainSunset"
    SoftRainSunset = "SoftRainSunset"
    Default = "Default"
