# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
from enum import Enum


class SimulationStatusName(Enum):
    CRASHED = "crashed"
    CREATED = "created"
    ENDED = "ended"
    FINISHED = "finished"
    INITIALIZED = "initialized"
    POSTPROCESSING = "postprocessing"
    QUEUED = "queued"
    STARTING = "starting"
    STOPPED = "stopped"
