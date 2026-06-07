"""Conservative quarterly staffing anomaly detection for public longitudinal charts.



Chart-adjusted nulls are visualization-only; raw PBJ values are always preserved.

"""



from __future__ import annotations



import statistics

from typing import Any



# Total / direct-care: absolute floor only (neighbor % drops are too noisy).

_TOTAL_ABS_THRESH = 0.25



# Role-specific floors; neighbor dip only when the home usually staffs that role.

_ROLE_PROFILES: dict[str, dict[str, float | None]] = {

    'rn': {

        'abs': 0.10,

        'neighbor_frac': 0.05,

        'neighbor_cap': 0.25,

        'typical_floor': None,

    },

    'lpn': {

        'abs': 0.05,

        'neighbor_frac': 0.05,

        'neighbor_cap': 0.12,

        'typical_floor': 0.20,

    },

    'aide': {

        'abs': 0.15,

        'neighbor_frac': 0.05,

        'neighbor_cap': 0.45,

        'typical_floor': 0.75,

    },

}





def _is_valid_number(val: Any) -> bool:

    if val is None:

        return False

    try:

        import math



        f = float(val)

        return math.isfinite(f)

    except (TypeError, ValueError):

        return False





def _series_typical_level(values: list[Any]) -> float | None:

    nums = [float(v) for v in values if _is_valid_number(v) and float(v) > 0]

    if len(nums) < 3:

        return None

    try:

        return float(statistics.median(nums))

    except statistics.StatisticsError:

        return None





def is_staffing_hprd_anomaly(

    value: Any,

    prior: Any,

    next_val: Any,

    *,

    label: str = 'hprd',

    profile: str = 'total',

    typical_level: float | None = None,

) -> tuple[bool, str | None]:

    """Return whether a quarterly HPRD value is an implausible data break."""

    if not _is_valid_number(value):

        return False, None

    v = float(value)

    reasons: list[str] = []



    if profile == 'total':

        if v < _TOTAL_ABS_THRESH:

            reasons.append(f'{label} below {_TOTAL_ABS_THRESH}')

    else:

        spec = _ROLE_PROFILES.get(profile) or _ROLE_PROFILES['rn']

        abs_thresh = float(spec['abs'])

        if v < abs_thresh:

            reasons.append(f'{label} below {abs_thresh}')



        neighbor_frac = spec.get('neighbor_frac')

        neighbor_cap = spec.get('neighbor_cap')

        typical_floor = spec.get('typical_floor')

        use_neighbor = (

            neighbor_frac is not None

            and neighbor_cap is not None

            and typical_level is not None

            and (typical_floor is None or typical_level >= float(typical_floor))

        )

        if use_neighbor and _is_valid_number(prior) and _is_valid_number(next_val):

            p = float(prior)

            n = float(next_val)

            frac = float(neighbor_frac)

            cap = float(neighbor_cap)

            if (

                p > 0

                and n > 0

                and v < cap

                and v < frac * p

                and v < frac * n

            ):

                reasons.append(

                    f'{label} below {frac:.0%} of prior and next valid quarters'

                )



    if not reasons:

        return False, None

    return True, '; '.join(reasons)





def apply_staffing_series_anomalies(

    quarters: list[str],

    total_series: list[Any],

    direct_series: list[Any] | None = None,

    *,

    ccn: str | None = None,

    profile: str = 'total',

) -> dict[str, Any]:

    """Build chart-safe series with anomaly metadata. Raw values are never overwritten."""

    raw_total = list(total_series or [])

    raw_direct = list(direct_series) if direct_series is not None else None

    n = len(quarters or [])

    chart_total: list[Any] = []

    chart_direct: list[Any] | None = [] if raw_direct is not None else None

    is_anomaly: list[bool] = []

    anomaly_reasons: list[str | None] = []

    records: list[dict[str, Any]] = []



    typical_total = _series_typical_level(raw_total) if profile != 'total' else None

    typical_direct = (

        _series_typical_level(raw_direct) if profile != 'total' and raw_direct is not None else None

    )



    for i in range(n):

        rt = raw_total[i] if i < len(raw_total) else None

        rd = raw_direct[i] if raw_direct is not None and i < len(raw_direct) else None

        prior = raw_total[i - 1] if i > 0 else None

        nxt = raw_total[i + 1] if i < n - 1 else None

        total_flag, total_reason = is_staffing_hprd_anomaly(

            rt,

            prior,

            nxt,

            label='total_hprd' if profile == 'total' else f'{profile}_hprd',

            profile=profile,

            typical_level=typical_total,

        )



        direct_flag = False

        direct_reason = None

        if raw_direct is not None:

            dprior = raw_direct[i - 1] if i > 0 else None

            dnxt = raw_direct[i + 1] if i < n - 1 else None

            direct_flag, direct_reason = is_staffing_hprd_anomaly(

                rd,

                dprior,

                dnxt,

                label='direct_hprd' if profile == 'total' else f'{profile}_direct_hprd',

                profile=profile,

                typical_level=typical_direct if typical_direct is not None else typical_total,

            )

            # Admin-heavy RN/LPN homes often have low direct-care HPRD while total role HPRD is plausible.
            if (
                profile in ('rn', 'lpn')
                and direct_flag
                and not total_flag
                and _is_valid_number(rt)
            ):
                healthy_floor = 0.15 if profile == 'rn' else 0.12
                if float(rt) >= healthy_floor:
                    direct_flag = False
                    direct_reason = None



        flagged = total_flag or direct_flag

        combined_reason = None

        if flagged:

            parts = []

            if total_reason:

                parts.append(total_reason)

            if direct_reason:

                parts.append(direct_reason)

            combined_reason = '; '.join(parts)



        is_anomaly.append(flagged)

        anomaly_reasons.append(combined_reason)

        chart_total.append(None if total_flag else rt)

        if chart_direct is not None:

            chart_direct.append(None if direct_flag else rd)



        if flagged:

            records.append(

                {

                    'ccn': (str(ccn).strip().zfill(6) if ccn else None),

                    'quarter': quarters[i],

                    'is_staffing_anomaly': True,

                    'anomaly_reason': combined_reason,

                    'raw_total_hprd': rt,

                    'raw_direct_hprd': rd,

                    'chart_total_hprd': None if total_flag else rt,

                    'chart_direct_hprd': None if direct_flag else rd,

                }

            )



    return {

        'chart_total': chart_total,

        'chart_direct': chart_direct,

        'raw_total': raw_total,

        'raw_direct': raw_direct,

        'is_staffing_anomaly': is_anomaly,

        'anomaly_reason': anomaly_reasons,

        'anomalies': records,

        'anomaly_count': len(records),

        'profile': profile,

    }


