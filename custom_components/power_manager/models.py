from dataclasses import dataclass, field
from enum import Enum


class OperatingMode(str, Enum):
    NORMAL = "normal"
    SURPLUS = "surplus"


@dataclass
class ControllableLoad:
    """
    Allgemeiner regelbarer Verbraucher.

    priority:
        1 = höchste Priorität.

    requested_kw:
        Aktuell angeforderte Leistung.

    actual_kw:
        Gemessene Istleistung.
        None = kein eigener Leistungsmesswert vorhanden.

    min_kw / max_kw:
        Technische Leistungsgrenzen.

    start_margin_kw:
        Zusätzliche Reserve zum Starten.

        Beispiel:
        min_kw = 6.0
        start_margin_kw = 0.3

        Start erst ab 6.3 kW verfügbarem Budget.

    stop_margin_kw:
        Haltereserve für bereits laufende Verbraucher.

        Muss <= start_margin_kw sein.

    min_on_time_s:
        Gewünschte Mindestlaufzeit.

        PMAX hat trotzdem immer Vorrang.

    min_off_time_s:
        Gewünschte Mindestauszeit.

    settling_time_s:
        Zeit nach einer Sollwertänderung, in der
        keine weitere Erhöhung erfolgen soll.

        Reduzierungen bleiben jederzeit erlaubt.
    """

    name: str
    priority: int

    requested_kw: float
    min_kw: float
    max_kw: float

    actual_kw: float | None = None

    available: bool = True

    can_modulate: bool = True
    can_shutdown: bool = True

    peak_shaving_enabled: bool = True
    surplus_enabled: bool = True

    start_margin_kw: float = 0.0
    stop_margin_kw: float = 0.0

    min_on_time_s: float = 0.0
    min_off_time_s: float = 0.0
    settling_time_s: float = 0.0


@dataclass
class LoadRuntimeState:
    """
    Laufender Zustand eines Verbrauchers.
    """

    is_on: bool = False

    last_target_kw: float = 0.0

    last_switch_s: float | None = None

    last_target_change_s: float | None = None

    settling_until_s: float | None = None


@dataclass
class ControllerInputs:
    """
    Globale Eingänge des Energiemanagers.

    grid_kw:
        positiv = Netzbezug
        negativ = Netzeinspeisung

    grid_limit_kw:
        Hartes PMAX am Netzanschlusspunkt.

    pv_kw:
        PV-Leistung.
        Im Überschussbetrieb bildet sie das Rohbudget
        für priorisierte Überschussverbraucher.

    battery_soc:
        Ladezustand 0...100 %.
        None = kein SOC-Wert vorhanden.

    battery_kw:
        positiv = Batterie entlädt
        negativ = Batterie lädt

    surplus_min_battery_soc:
        Optionaler Mindest-SOC / Reserve-SOC für den
        Überschussbetrieb.

        None = SOC-Grenze deaktiviert.

        Im Home-Assistant-Adapter wird bei Erreichen
        oder Unterschreiten dieser Grenze automatisch
        auf NORMAL zurückgeschaltet. Der reine Kern
        sperrt im SURPLUS-Modus bei <= Grenze ebenfalls
        die Überschussfreigabe.

    now_s:
        Zeitwert in Sekunden.

        Der Controller verwendet absichtlich keine
        eigene Systemzeit. Dadurch ist er vollständig
        reproduzierbar und testbar.
    """

    grid_kw: float
    grid_limit_kw: float

    pv_kw: float = 0.0

    battery_soc: float | None = None
    battery_kw: float = 0.0

    grid_reserve_kw: float = 0.0

    mode: OperatingMode = OperatingMode.NORMAL

    now_s: float = 0.0

    surplus_min_battery_soc: float | None = None


@dataclass
class ControllerState:
    """
    Zustand zwischen zwei Regeldurchläufen.
    """

    last_targets_kw: dict[str, float] = field(
        default_factory=dict
    )

    load_states: dict[str, LoadRuntimeState] = field(
        default_factory=dict
    )


@dataclass
class ControllerResult:
    """
    Ergebnis eines Regeldurchlaufs.

    Die zusätzlichen Diagnosewerte werden später
    sehr praktisch für Home-Assistant-Sensoren.
    """

    targets_kw: dict[str, float] = field(
        default_factory=dict
    )

    base_load_kw: float = 0.0

    measured_controlled_power_kw: float = 0.0
    estimated_controlled_power_kw: float = 0.0
    controlled_power_for_calculation_kw: float = 0.0

    effective_grid_limit_kw: float = 0.0

    peak_budget_kw: float = 0.0

    raw_surplus_budget_kw: float = 0.0
    surplus_budget_kw: float = 0.0

    available_budget_kw: float = 0.0
    unused_budget_kw: float = 0.0

    battery_discharge_kw: float = 0.0

    projected_grid_kw: float = 0.0
    grid_headroom_kw: float = 0.0

    total_requested_kw: float = 0.0
    total_target_kw: float = 0.0

    active_load_count: int = 0
    limited_load_count: int = 0
    settling_load_count: int = 0

    battery_soc_gate_enabled: bool = False
    battery_soc_blocking_surplus: bool = False

    peak_shaving_active: bool = False
    surplus_active: bool = False

    hard_limit_exceeded_now: bool = False

    grid_limit_unachievable: bool = False

    state: ControllerState = field(
        default_factory=ControllerState
    )