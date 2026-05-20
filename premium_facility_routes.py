"""Password-protected per-facility Premium dashboards served from Render (Flask).

Production note: Cloudflare may route ``/premium/<CCN>`` to Vercel by default. This module
registers explicit routes (e.g. ``/premium/075044``) on the main Flask app. Ensure that path
reaches Render, or open the Render service URL directly after deploy.
"""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING, Any

from flask import (
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

if TYPE_CHECKING:
    from flask import Flask, Response

_PREMIUM_FACILITIES: dict[str, dict[str, str]] = {
    '075044': {
        'name': 'Apple Rehab Farmington Valley',
        'city': 'Plainville',
        'state': 'CT',
        'password_env': 'PREMIUM_FACILITY_075044_PASSWORD',
        'password_default': 'ct-pbj320',
    },
}

_SESSION_PREFIX = 'premium_facility_auth_'


def _facility_password(ccn: str) -> str:
    meta = _PREMIUM_FACILITIES.get(ccn, {})
    return (os.environ.get(meta.get('password_env', '')) or meta.get('password_default') or '').strip()


def _is_authenticated(ccn: str) -> bool:
    return bool(session.get(f'{_SESSION_PREFIX}{ccn}'))


def _check_password(ccn: str, supplied: str) -> bool:
    expected = _facility_password(ccn)
    if not expected or not supplied:
        return False
    return secrets.compare_digest(supplied, expected)


def build_facility_metrics_payload(ccn: str, app_root: str) -> dict[str, Any]:
    """Build JSON payload for premium facility dashboard charts (quarterly PBJ + CMS provider info)."""
    prov = str(ccn).strip().zfill(6)
    meta = _PREMIUM_FACILITIES.get(prov, {})
    out: dict[str, Any] = {
        'ccn': prov,
        'facility_name': meta.get('name') or '',
        'city': meta.get('city') or '',
        'state': meta.get('state') or '',
        'quarters': [],
        'series': {
            'total_hprd': [],
            'rn_hprd': [],
            'lpn_hprd': [],
            'nurse_assistant_hprd': [],
            'census': [],
            'contract_pct': [],
        },
        'provider': {},
        'state_benchmark': {},
        'latest_quarter': None,
        'data_note': (
            'Quarterly PBJ aggregates from facility_quarterly_metrics.csv. '
            'Daily position-level PBJ can be added when source files are provisioned.'
        ),
    }
    try:
        import pandas as pd
    except ImportError:
        out['error'] = 'pandas not available'
        return out

    fq_path = os.path.join(app_root, 'facility_quarterly_metrics.csv')
    if os.path.isfile(fq_path):
        usecols = [
            'PROVNUM', 'PROVNAME', 'STATE', 'COUNTY_NAME', 'CY_Qtr', 'MDScensus',
            'Total_Nurse_HPRD', 'RN_HPRD', 'LPN_HPRD', 'Nurse_Assistant_HPRD', 'Contract_Percentage',
        ]
        try:
            header = set(pd.read_csv(fq_path, nrows=0).columns)
            usecols = [c for c in usecols if c in header]
            chunks = []
            for chunk in pd.read_csv(fq_path, usecols=usecols, low_memory=False, chunksize=100_000):
                if 'PROVNUM' not in chunk.columns:
                    continue
                norm = chunk['PROVNUM'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
                sub = chunk.loc[norm == prov]
                if not sub.empty:
                    chunks.append(sub)
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                if 'PROVNAME' in df.columns and not out['facility_name']:
                    out['facility_name'] = str(df['PROVNAME'].iloc[-1] or '').strip().title()
                if 'STATE' in df.columns:
                    out['state'] = str(df['STATE'].iloc[-1] or out['state']).strip().upper()[:2]
                if 'COUNTY_NAME' in df.columns:
                    out['county'] = str(df['COUNTY_NAME'].iloc[-1] or '').strip()
                df = df.sort_values('CY_Qtr')
                quarters = [str(q).strip() for q in df['CY_Qtr'].tolist()]
                out['quarters'] = quarters
                out['latest_quarter'] = quarters[-1] if quarters else None

                def _series(col: str) -> list:
                    if col not in df.columns:
                        return []
                    return [round(float(x), 4) if pd.notna(x) else None for x in df[col]]

                out['series']['total_hprd'] = _series('Total_Nurse_HPRD')
                out['series']['rn_hprd'] = _series('RN_HPRD')
                out['series']['lpn_hprd'] = _series('LPN_HPRD')
                out['series']['nurse_assistant_hprd'] = _series('Nurse_Assistant_HPRD')
                out['series']['census'] = _series('MDScensus')
                out['series']['contract_pct'] = _series('Contract_Percentage')

                latest_q = out['latest_quarter']
                st = out['state']
                if latest_q and st:
                    st_vals = []
                    for chunk in pd.read_csv(
                        fq_path, usecols=['STATE', 'CY_Qtr', 'Total_Nurse_HPRD'], low_memory=False, chunksize=150_000
                    ):
                        mask = (chunk['STATE'].astype(str).str.upper().str[:2] == st) & (
                            chunk['CY_Qtr'].astype(str) == str(latest_q)
                        )
                        vals = chunk.loc[mask, 'Total_Nurse_HPRD'].dropna()
                        st_vals.extend(vals.tolist())
                    if st_vals:
                        st_vals.sort()
                        mid = st_vals[len(st_vals) // 2]
                        out['state_benchmark'] = {
                            'quarter': latest_q,
                            'state': st,
                            'median_total_hprd': round(float(mid), 4),
                            'facility_count': len(st_vals),
                        }
        except Exception as e:
            out['error'] = f'facility_quarterly: {e}'

    pi_path = os.path.join(app_root, 'provider_info_combined_latest.csv')
    if os.path.isfile(pi_path):
        try:
            header = set(pd.read_csv(pi_path, nrows=0).columns)
            ccn_col = next(
                (c for c in ('ccn', 'PROVNUM', 'CCN', 'CMS Certification Number (CCN)') if c in header),
                None,
            )
            if ccn_col:
                for chunk in pd.read_csv(pi_path, low_memory=False, chunksize=100_000):
                    if ccn_col not in chunk.columns:
                        continue
                    norm = chunk[ccn_col].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
                    row = chunk.loc[norm == prov]
                    if row.empty:
                        continue
                    r = row.iloc[-1]
                    out['provider'] = {
                        'overall_rating': _safe_val(r, 'overall_rating'),
                        'staffing_rating': _safe_val(r, 'staffing_rating'),
                        'health_inspection_rating': _safe_val(r, 'health_inspection_rating'),
                        'qm_rating': _safe_val(r, 'quality_measure_rating', 'qm_rating'),
                        'reported_total_hprd': _safe_val(
                            r, 'reported_total_nurse_hrs_per_resident_per_day', 'Total_Nurse_HPRD'
                        ),
                        'case_mix_total_hprd': _safe_val(
                            r, 'case_mix_total_nurse_hrs_per_resident_per_day'
                        ),
                        'ownership_type': _safe_val(r, 'ownership_type', 'Ownership_Type'),
                        'avg_residents': _safe_val(r, 'avg_residents_per_day'),
                    }
                    pname = _safe_val(r, 'provider_name', 'PROVNAME', 'Provider Name')
                    if pname:
                        out['facility_name'] = str(pname).strip()
                    break
        except Exception as e:
            out.setdefault('warnings', []).append(f'provider_info: {e}')

    return out


def _safe_val(row, *keys):
    import pandas as pd

    for k in keys:
        if k not in row.index:
            continue
        v = row[k]
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        s = str(v).strip()
        if s and s.lower() not in ('nan', 'none', ''):
            return s
    return None


def _no_store_headers(resp: 'Response') -> 'Response':
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return resp


def register_premium_facility_routes(app: 'Flask', app_root: str) -> None:
    """Register password-protected ``/premium/<ccn>`` dashboards defined in this module."""

    for ccn, meta in _PREMIUM_FACILITIES.items():

        @app.route(f'/premium/{ccn}', methods=['GET', 'POST'], endpoint=f'premium_facility_{ccn}')
        @app.route(f'/premium/{ccn}/', methods=['GET', 'POST'], endpoint=f'premium_facility_{ccn}_slash')
        def premium_facility_dashboard(facility_ccn=ccn, facility_meta=meta):
            if request.method == 'POST':
                pwd = (request.form.get('password') or '').strip()
                if _check_password(facility_ccn, pwd):
                    session[f'{_SESSION_PREFIX}{facility_ccn}'] = True
                    session.permanent = True
                    return redirect(url_for(f'premium_facility_{facility_ccn}'))
                return _no_store_headers(
                    make_response(
                        render_template(
                            'premium_facility_login.html',
                            ccn=facility_ccn,
                            facility_name=facility_meta.get('name', ''),
                            error='Incorrect password.',
                        )
                    )
                )
            if not _is_authenticated(facility_ccn):
                return _no_store_headers(
                    make_response(
                        render_template(
                            'premium_facility_login.html',
                            ccn=facility_ccn,
                            facility_name=facility_meta.get('name', ''),
                            error=None,
                        )
                    )
                )
            payload = build_facility_metrics_payload(facility_ccn, app_root)
            return _no_store_headers(
                make_response(
                    render_template(
                        'premium_facility_dashboard.html',
                        ccn=facility_ccn,
                        facility_name=payload.get('facility_name') or facility_meta.get('name', ''),
                        city=payload.get('city') or facility_meta.get('city', ''),
                        state=payload.get('state') or facility_meta.get('state', ''),
                        metrics_json=payload,
                    )
                )
            )

        @app.route(f'/premium/{ccn}/api/metrics', endpoint=f'premium_facility_api_{ccn}')
        def premium_facility_metrics_api(facility_ccn=ccn):
            if not _is_authenticated(facility_ccn):
                return jsonify({'error': 'Unauthorized'}), 401
            return _no_store_headers(jsonify(build_facility_metrics_payload(facility_ccn, app_root)))

        @app.route(f'/premium/{ccn}/logout', endpoint=f'premium_facility_logout_{ccn}')
        def premium_facility_logout(facility_ccn=ccn):
            session.pop(f'{_SESSION_PREFIX}{facility_ccn}', None)
            return redirect(url_for(f'premium_facility_{facility_ccn}'))
