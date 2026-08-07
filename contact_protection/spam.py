"""Conservative, transparent spam scoring for contact submissions.

Secondary layer only. Media/press checkbox never increases trust or spam score.
One ordinary URL is allowed. High-confidence patterns only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contact_protection.config import SPAM_SCORE_THRESHOLD
from contact_protection.store import recent_duplicate_message

# External URLs (http/https). One is allowed; three+ is high confidence.
_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

# CAPTCHA-solving / automation-tool advertisements (no live promo domains in patterns).
_CAPTCHA_SOLVER_RE = re.compile(
    r'\b('
    r'xevil|2captcha|anti[\s-]?captcha|capmonster|deathbycaptcha|'
    r'captcha[\s-]?solver|solve[\s-]?captcha|bypass[\s-]?captcha|'
    r'recaptcha[\s-]?solver|hcaptcha[\s-]?solver|turnstile[\s-]?solver|'
    r'ruсaptcha|rucaptcha'
    r')\b',
    re.IGNORECASE,
)

# Bulk SEO / link-building solicitations.
_SEO_SOLICIT_RE = re.compile(
    r'('
    r'increase\s+your\s+(google\s+)?(search\s+)?ranking|'
    r'boost\s+your\s+(seo|search\s+rankings?)|'
    r'\bguest\s+posts?\b|'
    r'\blink\s+building\b|'
    r'\bseo\s+services?\b|'
    r'buy\s+(back)?links?\b|'
    r'cheap\s+(back)?links?\b|'
    r'improve\s+your\s+website\s+ranking|'
    r'submit\s+your\s+site\s+to\s+\d+\s+directories'
    r')',
    re.IGNORECASE,
)

# Credential theft / malware / executable promotion (high confidence).
_MALWARE_RE = re.compile(
    r'('
    r'\b(steal|harvest)\s+(passwords?|credentials?|cookies?)\b|'
    r'\b(keylogger|ransomware|trojan)\b|'
    r'\bdownload\s+our\s+\.exe\b|'
    r'\bfree\s+cracked\s+software\b'
    r')',
    re.IGNORECASE,
)

# Extreme character repetition (e.g. aaaaaaaaa...).
_REPEAT_RE = re.compile(r'(.)\1{19,}')

# Nonsensical machine-ish names: long consonant clusters / random tokens.
_MACHINE_NAME_RE = re.compile(
    r'^[a-z]{1,3}\d{4,}[a-z]*$|^[bcdfghjklmnpqrstvwxz]{8,}$',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpamAssessment:
    score: int
    reasons: tuple[str, ...]
    high_confidence: bool


def score_submission(*, name: str, message: str, is_press: bool = False) -> SpamAssessment:
    """Score a submission. ``is_press`` is ignored (informational only)."""
    del is_press  # never a trust or spam signal
    score = 0
    reasons: list[str] = []

    urls = _URL_RE.findall(message)
    if len(urls) >= 3:
        score += 4
        reasons.append('many_urls')
    elif len(urls) == 2:
        score += 1
        reasons.append('two_urls')

    if _CAPTCHA_SOLVER_RE.search(message):
        score += 5
        reasons.append('captcha_solver_ad')

    if _SEO_SOLICIT_RE.search(message):
        score += 5
        reasons.append('seo_solicitation')

    if _MALWARE_RE.search(message):
        score += 5
        reasons.append('malware_promo')

    if _REPEAT_RE.search(message) or _REPEAT_RE.search(name):
        score += 3
        reasons.append('extreme_repetition')

    if urls and _MACHINE_NAME_RE.match(name.strip()):
        score += 3
        reasons.append('machine_name_with_links')

    if recent_duplicate_message(message):
        score += 4
        reasons.append('duplicate_message')

    high = score >= SPAM_SCORE_THRESHOLD
    return SpamAssessment(score=score, reasons=tuple(reasons), high_confidence=high)
