"""Read-only audit for provider_snapshot_signals (Stage 0). Not for production."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

import provider_snapshot_signals as pss
import staffing_compliance_bundle as scb

Q_STATE = "2025Q4"
Q_COMP = scb.normalize_quarter(Q_STATE)
APP_ROOT = str(ROOT)


def main() -> None:
    fq_path = ROOT / "facility_quarterly_metrics.csv"
    if not fq_path.is_file():
        fq_path = ROOT / "facility_quarterly_metrics_latest.csv"
    fq = pd.read_csv(
        fq_path,
        usecols=["PROVNUM", "STATE", "CY_Qtr", "Total_Nurse_HPRD", "Nurse_Care_HPRD", "RN_HPRD", "avg_daily_census", "PROVNAME"],
        dtype={"PROVNUM": str},
    )
    fq["PROVNUM"] = fq["PROVNUM"].astype(str).str.zfill(6)
    fq_q = fq[fq["CY_Qtr"].astype(str) == Q_STATE].set_index("PROVNUM")

    state_df = pd.read_csv(ROOT / "state_quarterly_metrics.csv")
    state_df["STATE"] = state_df["STATE"].astype(str).str.upper()
    state_q = state_df[state_df["CY_Qtr"].astype(str) == Q_STATE].set_index("STATE")

    pi = pd.read_csv(ROOT / "provider_info/ProviderInfoNorm_2026_05.csv", low_memory=False)
    pi["ccn"] = pi["ccn"].astype(str).str.zfill(6)
    pi_by_ccn = pi.set_index("ccn")

    si_path = ROOT / "search_index.json"
    search_by_ccn: dict[str, dict] = {}
    if si_path.is_file():
        blob = json.loads(si_path.read_text(encoding="utf-8"))
        for item in blob.get("facilities") or blob.get("providers") or []:
            c = str(item.get("ccn", "")).zfill(6)
            if c:
                search_by_ccn[c] = item

    # casemix gap: vectorized
    joined = fq_q.join(
        pi_by_ccn[["case_mix_total_nurse_hrs_per_resident_per_day", "overall_rating", "staffing_rating", "abuse_icon", "provider_name"]],
        how="inner",
    )
    joined["cm"] = pd.to_numeric(joined["case_mix_total_nurse_hrs_per_resident_per_day"], errors="coerce")
    joined["gap_ratio"] = (joined["Total_Nurse_HPRD"] - joined["cm"]) / joined["cm"]
    casemix_ccn = joined["gap_ratio"].abs().idxmax() if len(joined) else None

    missing_ccn = next(iter(set(pi["ccn"]) - set(fq_q.index)), None)

    abuse = pi[pi["abuse_icon"].astype(str).str.upper().isin(["Y", "YES", "1", "TRUE"])]
    cms_ccn = abuse.iloc[0]["ccn"] if len(abuse) else None
    if cms_ccn is None:
        one = pi[pd.to_numeric(pi["overall_rating"], errors="coerce") == 1]
        cms_ccn = one.iloc[0]["ccn"] if len(one) else None

    scenarios = [
        ("1_ny_high_shortfall", "335003", "audit script NY below-threshold warning"),
        ("1_ny_high_shortfall_alt", "335261", "100% below days in bundle Q4"),
        ("2_ny_above_standard", "335092", "0 below direct-care days"),
        ("2_ny_above_standard_alt", "335513", "seagate audit CCN"),
        ("3_pa_non_screen", "395001", "PA no daily screen"),
        ("3_tx_non_screen", "675595", "TX non-screen state"),
        ("4_incomplete", missing_ccn, f"no facility_quarterly row for {Q_STATE}"),
        ("5_casemix_gap", casemix_ccn, "largest |reported-case_mix|/case_mix"),
        ("6_cms_flag", cms_ccn, "abuse icon or 1-star from ProviderInfoNorm"),
    ]

    results = []
    for key, ccn, note in scenarios:
        if not ccn:
            results.append({"scenario_key": key, "error": "no ccn found", "note": note})
            continue
        ccn = str(ccn).zfill(6)
        fr = fq_q.loc[ccn].to_dict() if ccn in fq_q.index else None
        pi_r = pi_by_ccn.loc[ccn].to_dict() if ccn in pi_by_ccn.index else {}
        st = str((fr or {}).get("STATE") or pi_r.get("state") or "").upper()[:2]
        comp = scb.lookup_public_summary(APP_ROOT, ccn, Q_COMP)
        reported = None
        direct = None
        if fr is not None and pd.notna(fr.get("Total_Nurse_HPRD")):
            reported = float(fr["Total_Nurse_HPRD"])
        if fr is not None and pd.notna(fr.get("Nurse_Care_HPRD")):
            direct = float(fr["Nurse_Care_HPRD"])
        savg = float(state_q.loc[st, "Total_Nurse_HPRD"]) if st in state_q.index else None
        signals = pss.build_facility_snapshot_signals(
            ccn=ccn,
            period=Q_COMP,
            period_display="Q4 2025",
            state_code=st,
            state_name={"NY": "New York", "CT": "Connecticut", "PA": "Pennsylvania", "TX": "Texas"}.get(st, st),
            reported_total_hprd=reported,
            state_average_hprd=savg,
            observed_display=f"{reported:.2f}" if reported is not None else "N/A",
            state_average_display=f"{savg:.2f}" if savg is not None else "N/A",
            compliance_summary=comp,
        )
        cms_reasons = []
        if str(pi_r.get("abuse_icon", "")).upper() in ("Y", "YES", "1", "TRUE"):
            cms_reasons.append("Abuse")
        for fld, lbl in [("overall_rating", "1-star overall"), ("staffing_rating", "1-star staffing")]:
            try:
                v = pi_r.get(fld)
                if v is not None and int(round(float(v))) == 1:
                    cms_reasons.append(lbl)
            except (TypeError, ValueError):
                pass
        cm_total = pd.to_numeric(pi_r.get("case_mix_total_nurse_hrs_per_resident_per_day"), errors="coerce")
        gap = None
        if reported is not None and pd.notna(cm_total) and float(cm_total) > 0:
            gap = (reported - float(cm_total)) / float(cm_total)
        results.append(
            {
                "scenario_key": key,
                "note": note,
                "ccn": ccn,
                "name": (fr or {}).get("PROVNAME") or pi_r.get("provider_name"),
                "state": st,
                "facility_quarter_row": (
                    {k: fr.get(k) for k in ["Total_Nurse_HPRD", "Nurse_Care_HPRD", "RN_HPRD", "avg_daily_census"]} if fr else None
                ),
                "state_average_total_hprd": savg,
                "compliance_summary": comp,
                "provider_info_flags": {
                    "overall_rating": pi_r.get("overall_rating"),
                    "staffing_rating": pi_r.get("staffing_rating"),
                    "abuse_icon": pi_r.get("abuse_icon"),
                    "case_mix_total": float(cm_total) if pd.notna(cm_total) else None,
                    "case_mix_gap_ratio": round(gap, 3) if gap is not None else None,
                },
                "cms_reasons_unstructured": cms_reasons,
                "search_risk_flag": (search_by_ccn.get(ccn) or {}).get("risk_flag") or (search_by_ccn.get(ccn) or {}).get("risk"),
                "signals_produced": [
                    {k: s.get(k) for k in ["metric_id", "direction", "display_label", "explanation", "comparator", "data_quality", "period", "period_display"]}
                    for s in signals
                ],
                "signal_count": len(signals),
            }
        )
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
