"""Household power balance, distinct from the grid-relative allocator base."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class HouseBalance:
    house_kw: float
    base_kw: float
    raw_base_kw: float
    estimated: bool
    source: str


def calculate_house_balance(
    *, grid_kw: float, pv_kw: float, battery_kw: float,
    consumer_kw: float, house_meter_kw: float | None = None,
    consumer_estimated: bool = False,
) -> HouseBalance:
    """Grid import + PV + battery discharge = household consumption.

    An optional total-house meter bypasses this reconstruction. Battery charging
    is negative and therefore does not get counted as household base demand.
    """

    values = (grid_kw, pv_kw, battery_kw, consumer_kw)
    if not all(isfinite(v) for v in values) or consumer_kw < 0:
        raise ValueError("Ungültige Leistungsbilanz.")
    if house_meter_kw is not None and (not isfinite(house_meter_kw) or house_meter_kw < 0):
        raise ValueError("Hausverbrauchszähler muss eine nichtnegative Leistung liefern.")
    total = house_meter_kw if house_meter_kw is not None else grid_kw + pv_kw + battery_kw
    raw_base = total - consumer_kw
    return HouseBalance(
        house_kw=max(0.0, total), base_kw=max(0.0, raw_base), raw_base_kw=raw_base,
        estimated=consumer_estimated,
        source="house_meter" if house_meter_kw is not None else "grid_pv_battery",
    )
