"""Closed-loop temporal pulse shaping: scope feedback drives AWG corrections.

Layers (imports only point downwards):
    core      - pure numpy logic, no GUI and no EPICS
    hardware  - scope/AWG drivers and simulators behind small interfaces
"""
