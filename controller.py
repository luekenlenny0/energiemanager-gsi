from math import isfinite

from allocator import (
    EPSILON,
    allocate_power,
)

from models import (
    ControllableLoad,
    ControllerInputs,
    ControllerResult,
    ControllerState,
    LoadRuntimeState,
    OperatingMode,
)


def _require_finite(
    name: str,
    value: float,
) -> None:
    """
    Verhindert NaN und unendliche Werte.

    Solche Werte könnten sonst sämtliche
    Leistungsberechnungen unbrauchbar machen.
    """

    if not isfinite(value):

        raise ValueError(
            f"{name} muss eine endliche Zahl sein."
        )


def _validate_load(
    load: ControllableLoad,
) -> None:
    """
    Plausibilitätsprüfung eines Verbrauchers.
    """

    if not load.name.strip():

        raise ValueError(
            "Verbrauchername darf nicht leer sein."
        )

    if (
        isinstance(
            load.priority,
            bool,
        )
        or not isinstance(
            load.priority,
            int,
        )
        or load.priority < 1
    ):

        raise ValueError(
            f"{load.name}: Priorität muss eine "
            f"ganze Zahl >= 1 sein."
        )

    numeric_values = {
        "requested_kw": (
            load.requested_kw
        ),
        "min_kw": (
            load.min_kw
        ),
        "max_kw": (
            load.max_kw
        ),
        "start_margin_kw": (
            load.start_margin_kw
        ),
        "stop_margin_kw": (
            load.stop_margin_kw
        ),
        "min_on_time_s": (
            load.min_on_time_s
        ),
        "min_off_time_s": (
            load.min_off_time_s
        ),
        "settling_time_s": (
            load.settling_time_s
        ),
    }

    if load.actual_kw is not None:

        numeric_values[
            "actual_kw"
        ] = load.actual_kw

    for (
        field_name,
        value,
    ) in numeric_values.items():

        _require_finite(
            f"{load.name}: {field_name}",
            value,
        )

    if (
        load.actual_kw is not None
        and load.actual_kw < 0.0
    ):

        raise ValueError(
            f"{load.name}: actual_kw darf "
            f"nicht negativ sein."
        )

    if load.min_kw < 0.0:

        raise ValueError(
            f"{load.name}: min_kw darf "
            f"nicht negativ sein."
        )

    if load.max_kw <= 0.0:

        raise ValueError(
            f"{load.name}: max_kw muss "
            f"größer als 0 sein."
        )

    if load.min_kw > load.max_kw:

        raise ValueError(
            f"{load.name}: min_kw darf nicht "
            f"größer als max_kw sein."
        )

    if (
        load.start_margin_kw < 0.0
        or load.stop_margin_kw < 0.0
    ):

        raise ValueError(
            f"{load.name}: Hysteresemargen "
            f"dürfen nicht negativ sein."
        )

    if (
        load.stop_margin_kw
        > load.start_margin_kw
    ):

        raise ValueError(
            f"{load.name}: stop_margin_kw darf "
            f"nicht größer als start_margin_kw sein."
        )

    if (
        load.min_on_time_s < 0.0
        or load.min_off_time_s < 0.0
        or load.settling_time_s < 0.0
    ):

        raise ValueError(
            f"{load.name}: Zeitwerte dürfen "
            f"nicht negativ sein."
        )

    # Ein Verbraucher, den unser Regler aktiv
    # fürs Peakshaving benutzt, muss im Notfall
    # vollständig abschaltbar sein.
    if (
        load.peak_shaving_enabled
        and not load.can_shutdown
    ):

        raise ValueError(
            f"{load.name}: Eine Peakshaving-Last "
            f"muss abschaltbar sein."
        )

    if (
        load.surplus_enabled
        and not load.can_shutdown
    ):

        raise ValueError(
            f"{load.name}: Eine Überschusslast "
            f"muss abschaltbar sein."
        )


def _validate_configuration(
    inputs: ControllerInputs,
    loads: list[ControllableLoad],
) -> None:
    """
    Globale Plausibilitätsprüfung.
    """

    input_values = {
        "grid_kw": (
            inputs.grid_kw
        ),
        "grid_limit_kw": (
            inputs.grid_limit_kw
        ),
        "pv_kw": (
            inputs.pv_kw
        ),
        "battery_kw": (
            inputs.battery_kw
        ),
        "grid_reserve_kw": (
            inputs.grid_reserve_kw
        ),
        "now_s": (
            inputs.now_s
        ),
    }

    for (
        field_name,
        value,
    ) in input_values.items():

        _require_finite(
            field_name,
            value,
        )

    if inputs.battery_soc is not None:

        _require_finite(
            "battery_soc",
            inputs.battery_soc,
        )

        if not (
            0.0
            <= inputs.battery_soc
            <= 100.0
        ):

            raise ValueError(
                "battery_soc muss zwischen "
                "0 und 100 liegen."
            )

    if (
        inputs.surplus_min_battery_soc
        is not None
    ):

        _require_finite(
            "surplus_min_battery_soc",
            inputs.surplus_min_battery_soc,
        )

        if not (
            0.0
            <= inputs.surplus_min_battery_soc
            <= 100.0
        ):

            raise ValueError(
                "surplus_min_battery_soc muss "
                "zwischen 0 und 100 liegen."
            )

        if inputs.battery_soc is None:

            raise ValueError(
                "surplus_min_battery_soc benötigt "
                "einen battery_soc-Wert."
            )

    if inputs.grid_limit_kw <= 0.0:

        raise ValueError(
            "grid_limit_kw muss größer als 0 sein."
        )

    if inputs.grid_reserve_kw < 0.0:

        raise ValueError(
            "grid_reserve_kw darf nicht negativ sein."
        )

    if (
        inputs.grid_reserve_kw
        >= inputs.grid_limit_kw
    ):

        raise ValueError(
            "grid_reserve_kw muss kleiner als "
            "grid_limit_kw sein."
        )

    if inputs.now_s < 0.0:

        raise ValueError(
            "now_s darf nicht negativ sein."
        )

    names = [
        load.name
        for load in loads
    ]

    if len(names) != len(set(names)):

        raise ValueError(
            "Jeder Verbraucher benötigt einen "
            "eindeutigen Namen."
        )

    for load in loads:

        _validate_load(
            load
        )


def _get_previous_runtime(
    load: ControllableLoad,
    state: ControllerState,
) -> LoadRuntimeState:
    """
    Vorherigen Laufzustand abrufen.

    Alte Sollwerte werden automatisch an
    die aktuellen Gerätegrenzen angepasst.
    """

    runtime = state.load_states.get(
        load.name
    )

    if runtime is not None:

        previous_target = max(
            0.0,
            min(
                runtime.last_target_kw,
                load.max_kw,
            ),
        )

        return LoadRuntimeState(
            is_on=(
                runtime.is_on
                and previous_target > EPSILON
            ),

            last_target_kw=(
                previous_target
            ),

            last_switch_s=(
                runtime.last_switch_s
            ),

            last_target_change_s=(
                runtime.last_target_change_s
            ),

            settling_until_s=(
                runtime.settling_until_s
            ),
        )

    previous_target = max(
        0.0,
        min(
            state.last_targets_kw.get(
                load.name,
                0.0,
            ),
            load.max_kw,
        ),
    )

    return LoadRuntimeState(
        is_on=(
            previous_target > EPSILON
        ),
        last_target_kw=(
            previous_target
        ),
    )


def _calculate_controlled_power(
    loads: list[ControllableLoad],
    state: ControllerState,
) -> tuple[float, float]:
    """
    Bestimmt bekannte Leistung der
    regelbaren Verbraucher.

    Istwert vorhanden:
        Istwert verwenden.

    Kein Istwert:
        letzten Sollwert als Schätzung verwenden.
    """

    measured_kw = 0.0
    estimated_kw = 0.0

    for load in loads:

        if load.actual_kw is not None:

            measured_kw += (
                load.actual_kw
            )

        else:

            runtime = (
                _get_previous_runtime(
                    load=load,
                    state=state,
                )
            )

            estimated_kw += (
                runtime.last_target_kw
            )

    return (
        measured_kw,
        estimated_kw,
    )


def _build_next_state(
    loads: list[ControllableLoad],
    targets_kw: dict[str, float],
    previous_state: ControllerState,
    now_s: float,
) -> ControllerState:
    """
    Aktualisiert den Zustand nach einem Regeldurchlauf.
    """

    next_last_targets = (
        previous_state
        .last_targets_kw
        .copy()
    )

    next_load_states = (
        previous_state
        .load_states
        .copy()
    )

    for load in loads:

        if load.name not in targets_kw:
            continue

        target_kw = max(
            0.0,
            min(
                targets_kw[
                    load.name
                ],
                load.max_kw,
            ),
        )

        previous = (
            _get_previous_runtime(
                load=load,
                state=previous_state,
            )
        )

        new_is_on = (
            target_kw > EPSILON
        )

        if (
            new_is_on
            != previous.is_on
        ):

            last_switch_s = (
                now_s
            )

        else:

            last_switch_s = (
                previous.last_switch_s
            )

        target_changed = (
            abs(
                target_kw
                - previous.last_target_kw
            )
            > EPSILON
        )

        if target_changed:

            last_target_change_s = (
                now_s
            )

            settling_until_s = (
                now_s
                + load.settling_time_s
            )

        else:

            last_target_change_s = (
                previous
                .last_target_change_s
            )

            settling_until_s = (
                previous
                .settling_until_s
            )

        next_last_targets[
            load.name
        ] = target_kw

        next_load_states[
            load.name
        ] = LoadRuntimeState(
            is_on=new_is_on,

            last_target_kw=(
                target_kw
            ),

            last_switch_s=(
                last_switch_s
            ),

            last_target_change_s=(
                last_target_change_s
            ),

            settling_until_s=(
                settling_until_s
            ),
        )

    return ControllerState(
        last_targets_kw=(
            next_last_targets
        ),

        load_states=(
            next_load_states
        ),
    )


def run_controller(
    inputs: ControllerInputs,
    loads: list[ControllableLoad],
    state: ControllerState | None = None,
) -> ControllerResult:
    """
    Zentraler Energiemanager.

    Oberste Regel:

        PMAX hat Vorrang.

    Reihenfolge der Bedeutung:

        1. PMAX / Netzgrenze
        2. technische Min-/Max-Grenzen
        3. Prioritäten
        4. Überschussstrategie
        5. Hysterese
        6. Mindestlauf-/Mindestauszeit
        7. Einschwingzeit

    Keine Komfortfunktion darf PMAX absichtlich
    überschreiben.
    """

    if state is None:
        state = ControllerState()

    _validate_configuration(
        inputs=inputs,
        loads=loads,
    )

    # ------------------------------------------------------
    # 1. Verbraucher nach Betriebsmodus auswählen
    # ------------------------------------------------------

    if (
        inputs.mode
        == OperatingMode.NORMAL
    ):

        controlled_loads = [
            load
            for load in loads
            if load.peak_shaving_enabled
        ]

    elif (
        inputs.mode
        == OperatingMode.SURPLUS
    ):

        controlled_loads = [
            load
            for load in loads
            if (
                load.peak_shaving_enabled
                and load.surplus_enabled
            )
        ]

    else:

        raise ValueError(
            f"Unbekannter Betriebsmodus: "
            f"{inputs.mode}"
        )

    # ------------------------------------------------------
    # 2. Aktuell geregelte Leistung
    # ------------------------------------------------------

    (
        measured_controlled_power_kw,
        estimated_controlled_power_kw,
    ) = _calculate_controlled_power(
        loads=controlled_loads,
        state=state,
    )

    controlled_power_for_calculation_kw = (
        measured_controlled_power_kw
        + estimated_controlled_power_kw
    )

    # ------------------------------------------------------
    # 3. Basislast
    # ------------------------------------------------------

    base_load_kw = (
        inputs.grid_kw
        - controlled_power_for_calculation_kw
    )

    # ------------------------------------------------------
    # 4. Effektives PMAX
    # ------------------------------------------------------

    effective_grid_limit_kw = (
        inputs.grid_limit_kw
        - inputs.grid_reserve_kw
    )

    hard_limit_exceeded_now = (
        inputs.grid_kw
        > effective_grid_limit_kw
        + EPSILON
    )

    # Wenn bereits die Basislast selbst oberhalb
    # PMAX liegt, kann unser Lastmanager allein
    # die Grenze nicht mehr erreichen.
    grid_limit_unachievable = (
        base_load_kw
        > effective_grid_limit_kw
        + EPSILON
    )

    # ------------------------------------------------------
    # 5. Maximales Verbraucherbudget aus PMAX
    # ------------------------------------------------------

    peak_budget_kw = max(
        0.0,
        effective_grid_limit_kw
        - base_load_kw,
    )

    # ------------------------------------------------------
    # 6. Batterie
    # ------------------------------------------------------

    battery_discharge_kw = max(
        0.0,
        inputs.battery_kw,
    )

    battery_soc_gate_enabled = (
        inputs.surplus_min_battery_soc
        is not None
    )

    battery_soc_blocking_surplus = (
        False
    )

    raw_surplus_budget_kw = 0.0

    surplus_budget_kw = 0.0

    # ------------------------------------------------------
    # 7. Betriebsmodus
    # ------------------------------------------------------

    if (
        inputs.mode
        == OperatingMode.SURPLUS
    ):

        # Roh verfügbare Energie für die
        # Überschussverbraucher.
        #
        # Batterieentladung wird abgezogen,
        # damit gespeicherte Energie nicht als
        # PV-Überschuss interpretiert wird.
        raw_surplus_budget_kw = max(
            0.0,
            controlled_power_for_calculation_kw
            - inputs.grid_kw
            - battery_discharge_kw,
        )

        battery_soc_blocking_surplus = bool(
            battery_soc_gate_enabled
            and inputs.battery_soc
            < inputs.surplus_min_battery_soc
        )

        if (
            battery_soc_blocking_surplus
        ):

            surplus_budget_kw = 0.0

        else:

            surplus_budget_kw = (
                raw_surplus_budget_kw
            )

        # Selbst im Überschussbetrieb bleibt
        # PMAX hart.
        available_budget_kw = min(
            surplus_budget_kw,
            peak_budget_kw,
        )

    else:

        available_budget_kw = (
            peak_budget_kw
        )

    # ------------------------------------------------------
    # 8. Budget verteilen
    # ------------------------------------------------------

    targets_kw = allocate_power(
        loads=controlled_loads,

        available_budget_kw=(
            available_budget_kw
        ),

        state=state,

        now_s=inputs.now_s,
    )

    total_target_kw = sum(
        targets_kw.values()
    )

    # ------------------------------------------------------
    # 9. Prognostizierter Netzbezug
    # ------------------------------------------------------

    projected_grid_kw = (
        base_load_kw
        + total_target_kw
    )

    # Zusätzliche interne Schutzprüfung.
    if (
        not grid_limit_unachievable
        and projected_grid_kw
        > effective_grid_limit_kw
        + EPSILON
    ):

        raise RuntimeError(
            "Interner Sicherheitsfehler: "
            "Berechneter Sollwert würde "
            "PMAX überschreiten."
        )

    # ------------------------------------------------------
    # 10. Anforderungen
    # ------------------------------------------------------

    total_requested_kw = sum(
        max(
            0.0,
            min(
                load.requested_kw,
                load.max_kw,
            ),
        )
        for load in controlled_loads
        if load.available
    )

    peak_shaving_active = (
        hard_limit_exceeded_now
        or (
            total_requested_kw
            > peak_budget_kw
            + EPSILON
        )
    )

    # ------------------------------------------------------
    # 11. Zustand aktualisieren
    # ------------------------------------------------------

    next_state = _build_next_state(
        loads=controlled_loads,

        targets_kw=targets_kw,

        previous_state=state,

        now_s=inputs.now_s,
    )

    # ------------------------------------------------------
    # 12. Diagnosewerte
    # ------------------------------------------------------

    unused_budget_kw = max(
        0.0,
        available_budget_kw
        - total_target_kw,
    )

    grid_headroom_kw = (
        effective_grid_limit_kw
        - projected_grid_kw
    )

    active_load_count = sum(
        1
        for target_kw
        in targets_kw.values()
        if target_kw > EPSILON
    )

    limited_load_count = sum(
        1
        for load in controlled_loads
        if (
            load.available
            and max(
                0.0,
                min(
                    load.requested_kw,
                    load.max_kw,
                ),
            )
            > targets_kw.get(
                load.name,
                0.0,
            )
            + EPSILON
        )
    )

    settling_load_count = sum(
        1
        for load in controlled_loads
        if (
            (
                runtime
                := next_state
                .load_states
                .get(
                    load.name
                )
            )
            is not None
            and runtime.settling_until_s
            is not None
            and inputs.now_s
            < runtime.settling_until_s
        )
    )

    return ControllerResult(
        targets_kw=(
            targets_kw
        ),

        base_load_kw=(
            base_load_kw
        ),

        measured_controlled_power_kw=(
            measured_controlled_power_kw
        ),

        estimated_controlled_power_kw=(
            estimated_controlled_power_kw
        ),

        controlled_power_for_calculation_kw=(
            controlled_power_for_calculation_kw
        ),

        effective_grid_limit_kw=(
            effective_grid_limit_kw
        ),

        peak_budget_kw=(
            peak_budget_kw
        ),

        raw_surplus_budget_kw=(
            raw_surplus_budget_kw
        ),

        surplus_budget_kw=(
            surplus_budget_kw
        ),

        available_budget_kw=(
            available_budget_kw
        ),

        unused_budget_kw=(
            unused_budget_kw
        ),

        battery_discharge_kw=(
            battery_discharge_kw
        ),

        projected_grid_kw=(
            projected_grid_kw
        ),

        grid_headroom_kw=(
            grid_headroom_kw
        ),

        total_requested_kw=(
            total_requested_kw
        ),

        total_target_kw=(
            total_target_kw
        ),

        active_load_count=(
            active_load_count
        ),

        limited_load_count=(
            limited_load_count
        ),

        settling_load_count=(
            settling_load_count
        ),

        battery_soc_gate_enabled=(
            battery_soc_gate_enabled
        ),

        battery_soc_blocking_surplus=(
            battery_soc_blocking_surplus
        ),

        peak_shaving_active=(
            peak_shaving_active
        ),

        surplus_active=(
            inputs.mode
            == OperatingMode.SURPLUS
        ),

        hard_limit_exceeded_now=(
            hard_limit_exceeded_now
        ),

        grid_limit_unachievable=(
            grid_limit_unachievable
        ),

        state=(
            next_state
        ),
    )