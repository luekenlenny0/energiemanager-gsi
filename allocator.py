from collections import defaultdict
from math import inf

from models import (
    ControllableLoad,
    ControllerState,
    LoadRuntimeState,
)


EPSILON = 0.000001


def _clamp_request(
    load: ControllableLoad,
) -> float:
    """
    Begrenzung der Leistungsanforderung auf
    den Bereich 0...max_kw.
    """

    return max(
        0.0,
        min(
            load.requested_kw,
            load.max_kw,
        ),
    )


def _get_runtime_state(
    load: ControllableLoad,
    state: ControllerState,
) -> LoadRuntimeState:
    """
    Liefert einen sicheren Laufzustand.

    Ein gespeicherter alter Sollwert wird automatisch
    auf das aktuell konfigurierte max_kw begrenzt.

    Damit bleibt das System auch stabil, wenn Parameter
    während des Betriebs geändert werden.
    """

    existing = state.load_states.get(
        load.name
    )

    if existing is not None:

        previous_target = max(
            0.0,
            min(
                existing.last_target_kw,
                load.max_kw,
            ),
        )

        return LoadRuntimeState(
            is_on=(
                existing.is_on
                and previous_target > EPSILON
            ),

            last_target_kw=previous_target,

            last_switch_s=(
                existing.last_switch_s
            ),

            last_target_change_s=(
                existing.last_target_change_s
            ),

            settling_until_s=(
                existing.settling_until_s
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
        last_target_kw=previous_target,
    )


def _elapsed_time(
    now_s: float,
    previous_s: float | None,
) -> float:
    """
    Zeit seit einem Ereignis.

    None bedeutet:
    Das Ereignis ist noch nie aufgetreten.
    """

    if previous_s is None:
        return inf

    return max(
        0.0,
        now_s - previous_s,
    )


def _allocate_priority_group(
    loads: list[ControllableLoad],
    available_budget_kw: float,
    state: ControllerState,
    now_s: float,
) -> dict[str, float]:
    """
    Verteilt Leistung innerhalb EINER Prioritätsgruppe.

    Grundregeln:

    - Bereits laufende Verbraucher werden bevorzugt.
    - Keine Round-Robin-Logik.
    - Reihenfolge bleibt stabil.
    - Gleiche Priorität teilt verbleibende Leistung
      möglichst gleichmäßig.
    - Mindestleistungen werden eingehalten.
    - Hysterese wird berücksichtigt.
    - Einschwingzeit verhindert weitere Erhöhungen.
    - Reduzierungen bleiben immer möglich.
    - Das Leistungsbudget darf niemals überschritten werden.
    """

    budget_kw = max(
        0.0,
        available_budget_kw,
    )

    targets: dict[str, float] = {
        load.name: 0.0
        for load in loads
    }

    candidates = []

    for index, load in enumerate(loads):

        if not load.available:
            continue

        runtime = _get_runtime_state(
            load=load,
            state=state,
        )

        requested_kw = _clamp_request(
            load
        )

        # --------------------------------------------------
        # Einschwingzeit
        # --------------------------------------------------
        #
        # Während einer noch laufenden Einschwingzeit
        # wird keine weitere LeistungsERHÖHUNG erlaubt.
        #
        # Beispiel:
        #
        # letzter Sollwert = 5 kW
        # neuer Wunsch     = 10 kW
        #
        # solange settling aktiv:
        # maximal weiterhin 5 kW.
        #
        # Wenn PMAX eine Reduzierung auf 3 kW verlangt,
        # ist diese Reduzierung trotzdem sofort möglich.
        # --------------------------------------------------

        if (
            runtime.settling_until_s is not None
            and now_s
            < runtime.settling_until_s
        ):

            requested_kw = min(
                requested_kw,
                runtime.last_target_kw,
            )

        if requested_kw <= 0.0:
            continue

        if load.can_modulate:

            if requested_kw < load.min_kw:
                continue

            required_min_kw = (
                load.min_kw
            )

        else:

            # Nicht modulierbare Last:
            # volle Anforderung oder AUS.
            required_min_kw = (
                requested_kw
            )

        previous_on = (
            runtime.is_on
        )

        elapsed_since_switch_s = (
            _elapsed_time(
                now_s=now_s,
                previous_s=(
                    runtime.last_switch_s
                ),
            )
        )

        # --------------------------------------------------
        # Dynamische Start-/Stopplogik
        # --------------------------------------------------

        if previous_on:

            if (
                elapsed_since_switch_s
                < load.min_on_time_s
            ):

                # Während der Mindestlaufzeit reicht
                # technisch min_kw.
                #
                # PMAX bleibt trotzdem hart:
                # Ist selbst min_kw nicht möglich,
                # wird abgeschaltet.
                admission_threshold_kw = (
                    required_min_kw
                )

            else:

                admission_threshold_kw = (
                    required_min_kw
                    + load.stop_margin_kw
                )

        else:

            if (
                elapsed_since_switch_s
                < load.min_off_time_s
            ):
                continue

            admission_threshold_kw = (
                required_min_kw
                + load.start_margin_kw
            )

        candidates.append(
            {
                "index": index,
                "load": load,
                "requested_kw": (
                    requested_kw
                ),
                "required_min_kw": (
                    required_min_kw
                ),
                "admission_threshold_kw": (
                    admission_threshold_kw
                ),
                "previous_on": (
                    previous_on
                ),
            }
        )

    if not candidates:
        return targets

    # Bereits laufende Verbraucher zuerst.
    #
    # Danach stabile Konfigurationsreihenfolge.
    #
    # KEIN Round-Robin.
    candidates.sort(
        key=lambda item: (
            not item["previous_on"],
            item["index"],
        )
    )

    active_candidates = []

    admission_budget_kw = (
        budget_kw
    )

    for candidate in candidates:

        required_min_kw = (
            candidate[
                "required_min_kw"
            ]
        )

        threshold_kw = (
            candidate[
                "admission_threshold_kw"
            ]
        )

        if (
            admission_budget_kw
            + EPSILON
            < required_min_kw
        ):
            continue

        if (
            admission_budget_kw
            + EPSILON
            < threshold_kw
        ):
            continue

        active_candidates.append(
            candidate
        )

        admission_budget_kw -= (
            threshold_kw
        )

    # ------------------------------------------------------
    # Mindestleistungen zuweisen
    # ------------------------------------------------------

    for candidate in active_candidates:

        load = candidate[
            "load"
        ]

        targets[
            load.name
        ] = candidate[
            "required_min_kw"
        ]

    used_kw = sum(
        targets.values()
    )

    remaining_kw = max(
        0.0,
        budget_kw - used_kw,
    )

    # ------------------------------------------------------
    # Verbleibende Leistung fair verteilen
    # ------------------------------------------------------

    modulating_loads = [
        (
            candidate["load"],
            candidate["requested_kw"],
        )
        for candidate in active_candidates
        if candidate[
            "load"
        ].can_modulate
    ]

    while (
        remaining_kw > EPSILON
        and modulating_loads
    ):

        share_kw = (
            remaining_kw
            / len(modulating_loads)
        )

        consumed_kw = 0.0

        still_open = []

        for (
            load,
            requested_kw,
        ) in modulating_loads:

            current_target_kw = (
                targets[
                    load.name
                ]
            )

            additional_capacity_kw = max(
                0.0,
                requested_kw
                - current_target_kw,
            )

            add_kw = min(
                share_kw,
                additional_capacity_kw,
            )

            targets[
                load.name
            ] += add_kw

            consumed_kw += (
                add_kw
            )

            if (
                requested_kw
                - targets[load.name]
                > EPSILON
            ):

                still_open.append(
                    (
                        load,
                        requested_kw,
                    )
                )

        if consumed_kw <= EPSILON:
            break

        remaining_kw = max(
            0.0,
            remaining_kw
            - consumed_kw,
        )

        modulating_loads = (
            still_open
        )

    return targets


def allocate_power(
    loads: list[ControllableLoad],
    available_budget_kw: float,
    state: ControllerState | None = None,
    now_s: float = 0.0,
) -> dict[str, float]:
    """
    Verteilt das Gesamtbudget nach Prioritäten.

    PRIORITÄT:
        1 = höchste Priorität.

    HARTE REGEL:
        Summe aller Sollwerte <= available_budget_kw.

    Hysterese, Mindestlaufzeit und Einschwingzeit
    dürfen diese Grenze niemals überschreiben.
    """

    if state is None:
        state = ControllerState()

    remaining_kw = max(
        0.0,
        available_budget_kw,
    )

    targets: dict[str, float] = {
        load.name: 0.0
        for load in loads
    }

    priority_groups: dict[
        int,
        list[ControllableLoad],
    ] = defaultdict(list)

    for load in loads:

        priority_groups[
            load.priority
        ].append(load)

    for priority in sorted(
        priority_groups.keys()
    ):

        if remaining_kw <= EPSILON:
            break

        group_targets = (
            _allocate_priority_group(
                loads=(
                    priority_groups[
                        priority
                    ]
                ),
                available_budget_kw=(
                    remaining_kw
                ),
                state=state,
                now_s=now_s,
            )
        )

        used_by_group_kw = sum(
            group_targets.values()
        )

        for (
            load_name,
            target_kw,
        ) in group_targets.items():

            targets[
                load_name
            ] = target_kw

        remaining_kw = max(
            0.0,
            remaining_kw
            - used_by_group_kw,
        )

    return targets