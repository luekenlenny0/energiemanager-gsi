"""Runtime manual demand; every request still passes through the allocator."""

from dataclasses import dataclass
from math import isfinite

MANUAL_MODES = ("auto", "manual", "off")


@dataclass
class ManualControl:
    mode: str = "auto"
    power_kw: float = 0.0


def validate_manual_power(value: float, *, min_kw: float, max_kw: float) -> float:
    """Accept off or a physically representable demand, without rounding up."""

    value = float(value)
    if not isfinite(value) or not 0 <= value <= max_kw:
        raise ValueError(f"Sollwert muss zwischen 0 und {max_kw:g} kW liegen.")
    if 0 < value < min_kw - 1e-6:
        raise ValueError(f"Technische Mindestleistung ist {min_kw:g} kW; alternativ 0 wählen.")
    return value


def manual_requested_kw(automatic_kw: float, control: ManualControl) -> float:
    if control.mode == "auto":
        return automatic_kw
    if control.mode == "manual":
        return control.power_kw
    if control.mode == "off":
        return 0.0
    raise ValueError("Unbekannte manuelle Betriebsart.")
