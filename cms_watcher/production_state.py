"""Read PBJ320 production vintages from existing canonical files (no parallel truth)."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MONTH_ABBR = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


@dataclass(frozen=True)
class ProductionObservedState:
    source_id: str
    vintage_label: str | None
    detail: dict[str, Any]
    status_known: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _repo_root(root: Path | None = None) -> Path:
    return (root or Path(__file__).resolve().parents[1]).resolve()


def _parse_norm_month(path: Path) -> tuple[int, int] | None:
    m = re.search(r"ProviderInfoNorm_(\d{4})_(\d{2})", path.name, re.I)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    if 1 <= mo <= 12:
        return y, mo
    return None


def _latest_provider_norm(root: Path) -> tuple[str | None, dict[str, Any]]:
    provider_dir = root / "provider_info"
    best: tuple[int, int, Path] | None = None
    for path in provider_dir.glob("ProviderInfoNorm_*.csv"):
        parsed = _parse_norm_month(path)
        if not parsed:
            continue
        y, mo = parsed
        if best is None or (y, mo) > best[:2]:
            best = (y, mo, path)
    if best is None:
        return None, {"error": "no ProviderInfoNorm_*.csv found"}
    y, mo, path = best
    label = f"{MONTH_ABBR[mo]} {y}"
    detail: dict[str, Any] = {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "processing_month": f"{y:04d}-{mo:02d}",
        "label": label,
    }
    combined = root / "provider_info_combined_latest.csv"
    if combined.is_file():
        detail["combined_latest_path"] = "provider_info_combined_latest.csv"
        try:
            with combined.open(newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row:
                    detail["combined_sample_processing_date"] = row.get("processing_date")
                    detail["combined_sample_quarter"] = row.get("quarter")
        except OSError as exc:
            detail["combined_read_error"] = str(exc)
    return label, detail


def _pbj_quarter(root: Path) -> tuple[str | None, dict[str, Any]]:
    detail: dict[str, Any] = {}
    qpath = root / "latest_quarter_data.json"
    label = None
    if qpath.is_file():
        try:
            data = json.loads(qpath.read_text(encoding="utf-8"))
            label = data.get("quarter")
            detail["latest_quarter_data.json"] = {
                "quarter": data.get("quarter"),
                "quarter_display": data.get("quarter_display"),
            }
        except (OSError, json.JSONDecodeError) as exc:
            detail["latest_quarter_error"] = str(exc)

    nat = root / "national_quarterly_metrics.csv"
    if nat.is_file():
        quarters: list[str] = []
        try:
            with nat.open(newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    q = (row.get("CY_Qtr") or "").strip()
                    if q:
                        quarters.append(q)
            if quarters:
                quarters_sorted = sorted(set(quarters))
                detail["national_max_CY_Qtr"] = quarters_sorted[-1]
                detail["national_quarter_count"] = len(quarters_sorted)
                if not label:
                    label = quarters_sorted[-1]
        except OSError as exc:
            detail["national_read_error"] = str(exc)
    return label, detail


def _ownership_active(root: Path) -> tuple[str | None, dict[str, Any]]:
    policy_path = root / "ownership" / "ownership_release_policy.json"
    if not policy_path.is_file():
        return None, {"error": "ownership_release_policy.json missing"}
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"error": str(exc)}

    active = str(policy.get("active_release_date") or "").strip()
    releases = policy.get("releases") or {}
    entry = releases.get(active) if isinstance(releases, dict) else None
    detail: dict[str, Any] = {
        "active_release_date": active or None,
        "policy_path": "ownership/ownership_release_policy.json",
    }
    if isinstance(entry, dict):
        detail["ownership_source_filename"] = entry.get("ownership_source_filename")
        detail["enrollment_source_filename"] = entry.get("enrollment_source_filename")
        detail["enrollment_release_date"] = entry.get("enrollment_release_date")
        detail["provider_info_source_filename"] = entry.get("provider_info_source_filename")
        detail["pbj_period"] = entry.get("pbj_period")
        detail["status"] = entry.get("status")
        # Confirm file exists
        own_name = entry.get("ownership_source_filename")
        if own_name:
            own_path = root / "ownership" / str(own_name)
            detail["ownership_csv_present"] = own_path.is_file()
        enr_name = entry.get("enrollment_source_filename")
        if enr_name:
            enr_path = root / "ownership" / str(enr_name)
            detail["enrollment_csv_present"] = enr_path.is_file()
    return (active or None), detail


def _enrollment_active(root: Path) -> tuple[str | None, dict[str, Any]]:
    label, detail = _ownership_active(root)
    enr = detail.get("enrollment_release_date") or detail.get("enrollment_source_filename")
    if detail.get("enrollment_release_date"):
        return str(detail["enrollment_release_date"]), detail
    if isinstance(enr, str) and enr:
        m = re.search(r"(20\d{2}[._-]\d{2}[._-]\d{2})", enr)
        if m:
            return m.group(1).replace(".", "-").replace("_", "-"), detail
    return label, detail


def _chow_meta(root: Path) -> tuple[str | None, dict[str, Any]]:
    path = root / "chow_index.json"
    if not path.is_file():
        return None, {"error": "chow_index.json missing"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"error": str(exc)}
    meta = data.get("meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        return None, {"error": "chow_index.json missing meta"}
    label = meta.get("cms_release")
    detail = {
        "cms_release": meta.get("cms_release"),
        "coverage_date_max": meta.get("coverage_date_max"),
        "event_count": meta.get("event_count"),
        "generated_at": meta.get("generated_at"),
        "source_label": meta.get("source_label"),
    }
    return (str(label) if label else None), detail


def _chain_month(root: Path) -> tuple[str | None, dict[str, Any]]:
    ownership = root / "ownership"
    best: tuple[int, int, Path] | None = None
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    for path in ownership.glob("Nursing_Home_Chain_Performance_Measures_*.csv"):
        m = re.search(r"_([A-Za-z]{3})_(\d{4})\.csv$", path.name)
        if not m:
            continue
        mo = month_map.get(m.group(1).lower())
        if not mo:
            continue
        y = int(m.group(2))
        if best is None or (y, mo) > best[:2]:
            best = (y, mo, path)
    if best is None:
        return None, {"error": "no Nursing_Home_Chain_Performance_Measures_*.csv"}
    y, mo, path = best
    label = f"{MONTH_ABBR[mo]} {y}"
    return label, {
        "path": str(path.relative_to(root)).replace("\\", "/"),
        "label": label,
    }


def read_production_state(source_id: str, root: Path | None = None) -> ProductionObservedState:
    repo = _repo_root(root)
    if source_id == "provider_information":
        label, detail = _latest_provider_norm(repo)
        return ProductionObservedState(source_id, label, detail, status_known=label is not None)
    if source_id == "pbj_nurse_staffing":
        label, detail = _pbj_quarter(repo)
        return ProductionObservedState(source_id, label, detail, status_known=label is not None)
    if source_id in ("pbj_nonnurse_staffing", "pbj_employee_detail"):
        return ProductionObservedState(
            source_id,
            None,
            {
                "note": "Premium/PBJapp-only; public pbj-root vintage UNPROVEN from this repo alone.",
                "surfaces": ["premium"],
            },
            status_known=False,
        )
    if source_id == "snf_all_owners":
        label, detail = _ownership_active(repo)
        return ProductionObservedState(source_id, label, detail, status_known=bool(label))
    if source_id == "snf_enrollments":
        label, detail = _enrollment_active(repo)
        return ProductionObservedState(source_id, label, detail, status_known=bool(label))
    if source_id == "snf_chow":
        label, detail = _chow_meta(repo)
        return ProductionObservedState(source_id, label, detail, status_known=bool(label))
    if source_id == "chain_performance":
        label, detail = _chain_month(repo)
        return ProductionObservedState(source_id, label, detail, status_known=bool(label))
    return ProductionObservedState(
        source_id,
        None,
        {"error": f"no production probe for {source_id}"},
        status_known=False,
    )


def read_all_production_states(root: Path | None = None) -> dict[str, ProductionObservedState]:
    from .registry import SOURCE_REGISTRY

    return {src.source_id: read_production_state(src.source_id, root=root) for src in SOURCE_REGISTRY}
