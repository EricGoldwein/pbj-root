"""Public-safe metric, threshold, and methodology metadata for the free PBJ320 site.

Backend-first infrastructure inspired by source-transparency patterns in investigative
nursing-home reporting. Does not perform advanced forensic calculations (acuity gap,
dollarized gap, related-party extraction, causal ownership effects).

Verified from: data/public/*.json, pbj-wrapped/public/data/json/state_standards.json,
data/compliance/staffing_compliance_thresholds.json
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PUBLIC_METADATA_VERSION = '2'

VALID_SOURCE_TYPES = frozenset({
    'inspection_based',
    'payroll_based',
    'facility_reported',
    'pbj320_derived',
})

VALID_THRESHOLD_TYPES = frozenset({
    'legal_minimum',
    'benchmark',
    'estimated_standard',
    'proposed_standard',
})

REQUIRED_METRIC_FIELDS = frozenset({
    'metric_id',
    'public_label',
    'source_type',
    'public_caveat',
    'show_on_public_site',
})

BANNED_PUBLIC_TERMS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), label)
    for pat, label in (
        (r'\bfraud\b', 'fraud'),
        (r'\bfatal\s+neglect\b', 'fatal neglect'),
        (r'\bprofit\s+from\s+neglect\b', 'profit from neglect'),
        (r'\bcare\s+never\s+delivered\b', 'care never delivered'),
        (r'\bgaming\b', 'gaming'),
        (r'\bproves?\s+negligence\b', 'proves negligence'),
        (r'\billegal\s+staffing\b', 'illegal staffing'),
        (r'\bmoney\s+laundering\b', 'money laundering'),
        (r'\bkilling\s+people\b', 'killing people'),
        (r'\bexpose\s+facilities\b', 'expose facilities'),
        (r'\blitigation\s+weapon\b', 'litigation weapon'),
        (r'\bprofit\s+from\s+understaffing\b', 'profit from understaffing'),
        (r'\btunneling\b', 'tunneling'),
        (r'\bhidden\s+profit\b', 'hidden profit'),
        (r'\bself[- ]dealing\b', 'self-dealing'),
        (r'\bfinancial\s+extraction\b', 'financial extraction'),
        (r'\bprove[sd]?\s+violation\b', 'proves violation'),
        (r'\bconfirms?\s+neglect\b', 'confirms neglect'),
        (r'\bdemonstrates?\s+illegal\b', 'demonstrates illegal'),
        (r'\bcommitted\s+fraud\b', 'committed fraud'),
        (r'\bdeliberately\s+withheld\s+care\b', 'deliberately withheld care'),
        (r'\bsystematic\s+neglect\b', 'systematic neglect'),
        (r'\bpredatory\s+operator\b', 'predatory operator'),
        (r'\bownership\s+caused\b', 'ownership caused'),
        (r'\bacquisition[- ]driven\s+neglect\b', 'acquisition-driven neglect'),
    )
)

# Hard-coded operator/investigative-publisher references forbidden in public metadata.
FORBIDDEN_VENDOR_REFS: tuple[str, ...] = (
    'hunterbrook',
    'hunterbrook capital',
    'hunterbrook media',
    'hunterbrook law',
)

FORBIDDEN_OPERATOR_HARDCODING: tuple[str, ...] = (
    'ensign group',
    'ensign services',
    '$ensg',
)

# Patterns that must not appear in new pbj-root forensic calculation code paths.
FORBIDDEN_FORENSIC_PATTERNS: tuple[str, ...] = (
    'acuity_informed_staffing_gap',
    'dollarized_staffing_gap',
    'related_party_extraction',
    'pre_post_ownership_causal',
    'harrington_gap_dollars',
    'staffing_cost_savings',
)

ROOT = Path(__file__).resolve().parent
PUBLIC_DATA_DIR = ROOT / 'data' / 'public'
METRIC_REGISTRY_PATH = PUBLIC_DATA_DIR / 'public_metric_metadata.json'
METHODOLOGY_PATH = PUBLIC_DATA_DIR / 'public_methodology_snippets.json'
THRESHOLD_OVERRIDES_PATH = PUBLIC_DATA_DIR / 'public_threshold_overrides.json'
THRESHOLD_REGISTRY_PATH = PUBLIC_DATA_DIR / 'public_threshold_metadata.json'
ENRICHED_METADATA_PATH = PUBLIC_DATA_DIR / 'public_metadata_enriched.json'
INDEPENDENCE_GUARDRAILS_PATH = PUBLIC_DATA_DIR / 'public_independence_guardrails.json'

STATE_STANDARDS_PATHS = (
    ROOT / 'pbj-wrapped' / 'public' / 'data' / 'json' / 'state_standards.json',
    ROOT / 'state_standards.json',
)

COMPLIANCE_THRESHOLDS_PATH = ROOT / 'data' / 'compliance' / 'staffing_compliance_thresholds.json'

MACPAC_SOURCE_URL = 'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _app_root(app_root: str | None = None) -> Path:
    return Path(app_root or ROOT)


def _resolve_enriched_path(app_root: str | None = None) -> Path | None:
    """Optional pbjapp-enriched metadata (preferred when present)."""
    override = (os.environ.get('PBJ_PUBLIC_METADATA_ENRICHED') or '').strip()
    candidates: list[Path] = []
    if override:
        p = Path(override)
        candidates.append(p if p.is_absolute() else _app_root(app_root) / override)
    base = _app_root(app_root)
    candidates.extend([
        base / ENRICHED_METADATA_PATH.relative_to(ROOT),
        base / 'data' / 'public' / 'public_metadata_enriched.json',
    ])
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def load_independence_guardrails() -> dict[str, Any]:
    if not INDEPENDENCE_GUARDRAILS_PATH.is_file():
        return {}
    return _read_json(INDEPENDENCE_GUARDRAILS_PATH)


def evidence_tier_for_source_type(source_type: str) -> str:
    guard = load_independence_guardrails()
    mapping = guard.get('source_type_to_evidence_tier') or {}
    return str(mapping.get(source_type) or '')


@lru_cache(maxsize=1)
def load_methodology_snippets() -> dict[str, Any]:
    data = _read_json(METHODOLOGY_PATH)
    enriched = _resolve_enriched_path()
    if enriched:
        try:
            blob = _read_json(enriched)
            if isinstance(blob.get('snippets'), dict):
                merged = dict(data.get('snippets') or {})
                merged.update(blob['snippets'])
                data = {**data, 'snippets': merged}
            for key in ('source_type_labels', 'source_type_descriptions'):
                if isinstance(blob.get(key), dict):
                    merged = dict(data.get(key) or {})
                    merged.update(blob[key])
                    data = {**data, key: merged}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


@lru_cache(maxsize=1)
def load_metric_registry() -> dict[str, Any]:
    data = _read_json(METRIC_REGISTRY_PATH)
    enriched = _resolve_enriched_path()
    if enriched:
        try:
            blob = _read_json(enriched)
            extra = blob.get('metrics')
            if isinstance(extra, list) and extra:
                by_id = {m['metric_id']: m for m in data.get('metrics', []) if m.get('metric_id')}
                for row in extra:
                    mid = row.get('metric_id')
                    if mid:
                        by_id[mid] = {**by_id.get(mid, {}), **row}
                data = {**data, 'metrics': list(by_id.values())}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return data


def metrics_by_id() -> dict[str, dict[str, Any]]:
    reg = load_metric_registry()
    return {
        str(m['metric_id']): m
        for m in reg.get('metrics', [])
        if m.get('metric_id')
    }


def public_metrics() -> list[dict[str, Any]]:
    return [
        m for m in load_metric_registry().get('metrics', [])
        if m.get('show_on_public_site', True)
    ]


def get_source_badge(source_type: str) -> str:
    labels = load_methodology_snippets().get('source_type_labels') or {}
    return str(labels.get(source_type) or source_type.replace('_', ' ').title())


def get_source_type_description(source_type: str) -> str:
    desc = load_methodology_snippets().get('source_type_descriptions') or {}
    return str(desc.get(source_type) or '')


def premium_bridge_text(*, variant: str = 'default') -> str:
    snippets = load_methodology_snippets().get('snippets') or {}
    if variant == 'alt':
        return str(snippets.get('premium_bridge_alt') or snippets.get('premium_bridge') or '')
    return str(snippets.get('premium_bridge') or '')


def _load_state_standards() -> dict[str, Any]:
    for path in STATE_STANDARDS_PATHS:
        if path.is_file():
            try:
                return _read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
    return {}


def _threshold_type_for_macpac_row(row: dict[str, Any]) -> str:
    if str(row.get('Is_Federal_Minimum', '')).strip().lower() in ('true', '1', 'yes'):
        return 'legal_minimum'
    return 'estimated_standard'


def _macpac_threshold_entries() -> list[dict[str, Any]]:
    standards = _load_state_standards()
    entries: list[dict[str, Any]] = []
    for abbr, row in sorted(standards.items()):
        if not isinstance(row, dict):
            continue
        state = str(abbr).upper()[:2]
        min_val = row.get('Min_Staffing')
        max_val = row.get('Max_Staffing')
        value_type = str(row.get('Value_Type') or 'single').strip().lower()
        try:
            min_f = float(min_val) if min_val is not None else None
            max_f = float(max_val) if max_val is not None else None
        except (TypeError, ValueError):
            continue
        if min_f is None:
            continue
        th_type = _threshold_type_for_macpac_row(row)
        if value_type == 'range' and max_f is not None and max_f != min_f:
            value = max_f
            label_val = f'{min_f:g}–{max_f:g}'
        else:
            value = min_f
            label_val = f'{min_f:g}'
        entries.append({
            'state': state,
            'threshold_id': f'{state.lower()}_macpac_total_nurse_hprd',
            'public_label': f'{row.get("State") or state} MACPAC reference ({label_val} HPRD)',
            'value': value,
            'unit': 'total_nurse_hprd',
            'threshold_type': th_type,
            'short_caveat': 'MACPAC state policy compendium estimate for chart reference lines.',
            'methodology_caveat': (
                'PBJ320 uses MACPAC summaries as estimated reference lines unless a separate verified '
                'legal minimum is documented for that state.'
            ),
            'source_url_or_note': MACPAC_SOURCE_URL,
            'show_public': True,
            'min_value': min_f,
            'max_value': max_f if value_type == 'range' else min_f,
            'value_type': value_type,
        })
    return entries


def _override_threshold_entries() -> list[dict[str, Any]]:
    if not THRESHOLD_OVERRIDES_PATH.is_file():
        return []
    data = _read_json(THRESHOLD_OVERRIDES_PATH)
    return list(data.get('overrides') or [])


def _compliance_threshold_entries() -> list[dict[str, Any]]:
    """Daily-screen rules from staffing_screening_registry (metric + threshold composed)."""
    try:
        import staffing_screening_registry as ssr
    except ImportError:
        ssr = None
    if ssr is not None:
        return [ssr.rule_to_public_threshold_entry(r) for r in ssr.daily_screen_rules()]
    if not COMPLIANCE_THRESHOLDS_PATH.is_file():
        return []
    try:
        cfg = _read_json(COMPLIANCE_THRESHOLDS_PATH)
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for row in cfg.get('state_thresholds') or []:
        if not row.get('enabled', True):
            continue
        state = str(row.get('state', '')).upper()[:2]
        try:
            value = float(row['threshold'])
        except (KeyError, TypeError, ValueError):
            continue
        tid = f'{state.lower()}_pbj_daily_screen'
        out.append({
            'state': state,
            'threshold_id': tid,
            'public_label': str(row.get('label') or f'{state} PBJ daily screen'),
            'value': value,
            'unit': str(row.get('metric') or 'total_nurse_hprd'),
            'threshold_type': 'estimated_standard',
            'short_caveat': 'Used for PBJ320 daily staffing screening on facility pages.',
            'methodology_caveat': str(row.get('notes') or ''),
            'source_url_or_note': 'data/compliance/staffing_compliance_thresholds.json',
            'show_public': True,
        })
    return out


@lru_cache(maxsize=1)
def load_threshold_registry() -> dict[str, Any]:
    """Merge MACPAC state standards, compliance screens, and hand-curated overrides."""
    enriched = _resolve_enriched_path()
    if enriched:
        try:
            blob = _read_json(enriched)
            if isinstance(blob.get('thresholds'), list) and blob['thresholds']:
                return {
                    'schema_version': blob.get('schema_version', 1),
                    'description': blob.get('description') or 'Enriched threshold metadata from pbjapp',
                    'thresholds': blob['thresholds'],
                    'source': str(enriched),
                }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    if THRESHOLD_REGISTRY_PATH.is_file():
        try:
            cached = _read_json(THRESHOLD_REGISTRY_PATH)
            if cached.get('thresholds'):
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in _macpac_threshold_entries():
        key = (entry['state'], entry['threshold_id'])
        by_key[key] = entry
    for entry in _override_threshold_entries():
        key = (str(entry.get('state', '')).upper()[:2], str(entry.get('threshold_id', '')))
        if key[0] and key[1]:
            by_key[key] = entry
    for entry in _compliance_threshold_entries():
        key = (entry['state'], entry['threshold_id'])
        by_key[key] = entry

    thresholds = sorted(by_key.values(), key=lambda r: (r.get('state', ''), r.get('threshold_id', '')))
    return {
        'schema_version': 1,
        'description': 'Public staffing threshold metadata for PBJ320 free site',
        'thresholds': thresholds,
    }


def thresholds_for_state(state_code: str | None) -> list[dict[str, Any]]:
    st = (state_code or '').strip().upper()[:2]
    reg = load_threshold_registry()
    rows = [t for t in reg.get('thresholds', []) if t.get('show_public', True)]
    if not st:
        return rows
    return [t for t in rows if str(t.get('state', '')).upper()[:2] in (st, 'US')]


def page_bootstrap_payload(
    *,
    page_type: str = 'facility',
    state_code: str | None = None,
    metric_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Compact JSON for facility/state page templates (source badges, thresholds, snippets)."""
    snippets = load_methodology_snippets()
    metric_map = metrics_by_id()
    selected_metrics: list[dict[str, Any]] = []
    if metric_ids:
        for mid in metric_ids:
            m = metric_map.get(mid)
            if m and m.get('show_on_public_site', True):
                st = str(m.get('source_type', ''))
                selected_metrics.append({
                    **m,
                    'source_badge': get_source_badge(st),
                    'evidence_tier': evidence_tier_for_source_type(st),
                })
    else:
        default_ids = {
            'facility': (
                'total_nurse_hprd', 'rn_hprd', 'case_mix_cmi', 'abuse_icon',
                'state_percentile', 'threshold_shortfall_rate',
            ),
            'state': ('total_nurse_hprd', 'state_ranking', 'state_comparison'),
        }.get(page_type, ())
        for mid in default_ids:
            m = metric_map.get(mid)
            if m:
                st = str(m.get('source_type', ''))
                selected_metrics.append({
                    **m,
                    'source_badge': get_source_badge(st),
                    'evidence_tier': evidence_tier_for_source_type(st),
                })

    return {
        'version': PUBLIC_METADATA_VERSION,
        'page_type': page_type,
        'state_code': (state_code or '').upper()[:2] or None,
        'source_type_labels': snippets.get('source_type_labels') or {},
        'metrics': selected_metrics,
        'thresholds': thresholds_for_state(state_code),
        'snippets': {
            'metric_reliability': (snippets.get('snippets') or {}).get('metric_reliability'),
            'pbj320_derived': (snippets.get('snippets') or {}).get('pbj320_derived'),
            'state_thresholds': (snippets.get('snippets') or {}).get('state_thresholds'),
            'evidence_tiers': (snippets.get('snippets') or {}).get('evidence_tiers'),
            'independence_principle': (snippets.get('snippets') or {}).get('independence_principle'),
            'premium_bridge': premium_bridge_text(),
        },
        'independence_guardrails_version': (load_independence_guardrails().get('schema_version')),
    }


def render_metadata_bootstrap_script(payload: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Non-executing JSON script tag for template hooks."""
    blob = payload if payload is not None else page_bootstrap_payload(**kwargs)
    raw = json.dumps(blob, ensure_ascii=False, separators=(',', ':'))
    safe = raw.replace('<', '\\u003c').replace('>', '\\u003e')
    return (
        f'<script type="application/json" id="pbj-public-metadata-bootstrap">{safe}</script>'
    )


def public_metadata_api_bundle() -> dict[str, Any]:
    snippets = load_methodology_snippets()
    return {
        'version': PUBLIC_METADATA_VERSION,
        'metrics': public_metrics(),
        'thresholds': load_threshold_registry().get('thresholds', []),
        'methodology': snippets.get('snippets') or {},
        'source_type_labels': snippets.get('source_type_labels') or {},
        'source_type_descriptions': snippets.get('source_type_descriptions') or {},
        'premium_bridge': premium_bridge_text(),
        'premium_bridge_alt': premium_bridge_text(variant='alt'),
        'independence_guardrails': load_independence_guardrails(),
        'evidence_tiers': (load_independence_guardrails().get('evidence_tiers') or {}),
    }


def validate_metric_registry() -> list[str]:
    issues: list[str] = []
    reg = load_metric_registry()
    for i, m in enumerate(reg.get('metrics') or []):
        missing = REQUIRED_METRIC_FIELDS - set(m.keys())
        if missing:
            issues.append(f'metric[{i}] missing fields: {sorted(missing)}')
        st = m.get('source_type')
        if st not in VALID_SOURCE_TYPES:
            issues.append(f'metric {m.get("metric_id")}: invalid source_type {st!r}')
    return issues


def validate_threshold_registry() -> list[str]:
    issues: list[str] = []
    reg = load_threshold_registry()
    for i, t in enumerate(reg.get('thresholds') or []):
        tt = t.get('threshold_type')
        if tt not in VALID_THRESHOLD_TYPES:
            issues.append(f'threshold[{i}] {t.get("threshold_id")}: invalid threshold_type {tt!r}')
        for field in ('state', 'threshold_id', 'public_label', 'value', 'unit', 'threshold_type'):
            if field not in t:
                issues.append(f'threshold[{i}] missing {field}')
    return issues


def scan_banned_terms_in_public_copy() -> list[str]:
    """Flag sensational/legal terms in public metadata copy (not quoted-source contexts)."""
    hits: list[str] = []
    texts: list[tuple[str, str]] = []

    for m in load_metric_registry().get('metrics') or []:
        for key in ('public_label', 'plain_english_source', 'public_caveat'):
            val = m.get(key)
            if val:
                texts.append((f'metric:{m.get("metric_id")}:{key}', str(val)))

    snippets = load_methodology_snippets()
    for key, val in (snippets.get('snippets') or {}).items():
        texts.append((f'snippet:{key}', str(val)))
    for key, val in (snippets.get('source_type_labels') or {}).items():
        texts.append((f'source_type_label:{key}', str(val)))
    for key, val in (snippets.get('source_type_descriptions') or {}).items():
        texts.append((f'source_type_description:{key}', str(val)))

    for t in load_threshold_registry().get('thresholds') or []:
        for key in ('public_label', 'short_caveat', 'methodology_caveat'):
            val = t.get(key)
            if val:
                texts.append((f'threshold:{t.get("threshold_id")}:{key}', str(val)))

    guard = load_independence_guardrails()
    for key in ('core_principle',):
        val = guard.get(key)
        if val:
            texts.append((f'guardrails:{key}', str(val)))
    # implementation_rules and rejected_labels intentionally name forbidden examples; scan approved copy only.
    for slug, guidance in (guard.get('future_metric_label_guidance') or {}).items():
        if isinstance(guidance, dict):
            for gkey in ('approved_public_label', 'approved_caveat'):
                val = guidance.get(gkey)
                if val:
                    texts.append((f'guardrails:future_metric:{slug}:{gkey}', str(val)))

    for loc, text in texts:
        for pattern, label in BANNED_PUBLIC_TERMS:
            if pattern.search(text):
                hits.append(f'{loc}: banned term "{label}"')
    return hits


def scan_vendor_or_operator_hardcoding(root: Path | None = None) -> list[str]:
    """Flag Hunterbrook or Ensign-specific strings in public-facing metadata registries."""
    base = root or ROOT
    hits: list[str] = []
    allowed_blocklist = {'public_independence_guardrails.json'}
    scan_paths = [
        p for p in (base / 'data' / 'public').glob('*.json')
        if p.name not in allowed_blocklist
    ]
    for path in scan_paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace').lower()
        except OSError:
            continue
        rel = path.relative_to(base).as_posix()
        for term in FORBIDDEN_VENDOR_REFS:
            if term in text:
                hits.append(f'{rel}: prohibited vendor reference {term!r}')
        for term in FORBIDDEN_OPERATOR_HARDCODING:
            if term in text:
                hits.append(f'{rel}: prohibited operator hardcoding {term!r}')
    return hits


def validate_thresholds_have_documented_source() -> list[str]:
    issues: list[str] = []
    for t in load_threshold_registry().get('thresholds') or []:
        if not t.get('show_public', True):
            continue
        src = str(t.get('source_url_or_note') or '').strip()
        if not src:
            issues.append(f'threshold {t.get("threshold_id")}: missing source_url_or_note')
    return issues


def validate_independence_guardrails_present() -> list[str]:
    issues: list[str] = []
    guard = load_independence_guardrails()
    if not guard:
        return ['public_independence_guardrails.json missing or empty']
    for key in ('core_principle', 'evidence_tiers', 'implementation_rules'):
        if not guard.get(key):
            issues.append(f'independence guardrails missing {key}')
    return issues


def scan_rhetorical_conclusions_in_public_copy() -> list[str]:
    """Flag legal/conclusion phrasing beyond the banned-term list."""
    guard = load_independence_guardrails()
    extra_patterns = guard.get('rhetorical_conclusion_patterns_to_avoid') or []
    hits: list[str] = []
    texts: list[tuple[str, str]] = []
    for m in load_metric_registry().get('metrics') or []:
        texts.append((f'metric:{m.get("metric_id")}:public_caveat', str(m.get('public_caveat') or '')))
    for key, val in (load_methodology_snippets().get('snippets') or {}).items():
        texts.append((f'snippet:{key}', str(val)))
    for loc, text in texts:
        low = text.lower()
        for phrase in extra_patterns:
            if phrase.lower() in low:
                hits.append(f'{loc}: rhetorical conclusion pattern {phrase!r}')
    return hits


def scan_forbidden_forensic_patterns(root: Path | None = None) -> list[str]:
    """Ensure pbj-root does not add forensic calculator implementations in app code."""
    base = root or ROOT
    issues: list[str] = []
    impl_re = re.compile(
        r'^\s*(?:async\s+)?def\s+(' + '|'.join(re.escape(p) for p in FORBIDDEN_FORENSIC_PATTERNS) + r')\s*\(',
        re.IGNORECASE | re.MULTILINE,
    )
    for rel in ('app.py', 'public_metadata.py'):
        target = base / rel
        if not target.is_file():
            continue
        content = target.read_text(encoding='utf-8', errors='replace')
        for match in impl_re.finditer(content):
            issues.append(f'{rel}: forbidden forensic function def {match.group(1)!r}')
    return issues


def validate_all() -> list[str]:
    issues = (
        validate_metric_registry()
        + validate_threshold_registry()
        + validate_independence_guardrails_present()
        + validate_thresholds_have_documented_source()
        + scan_banned_terms_in_public_copy()
        + scan_rhetorical_conclusions_in_public_copy()
        + scan_vendor_or_operator_hardcoding()
        + scan_forbidden_forensic_patterns()
    )
    try:
        import staffing_screening_registry as ssr

        issues.extend(ssr.validate_daily_screen_rules())
    except ImportError:
        pass
    return issues


def write_threshold_registry_cache() -> Path:
    """Materialize merged threshold registry for audits and offline review."""
    reg = load_threshold_registry()
    THRESHOLD_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    THRESHOLD_REGISTRY_PATH.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    return THRESHOLD_REGISTRY_PATH
