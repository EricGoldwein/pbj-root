"""Download approved staffing day-evidence gzip from GitHub Release (manifest pointer)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import staffing_evidence_bundle as seb  # noqa: E402


def _log(msg: str) -> None:
    print(f"[download_staffing_evidence_bundle] {msg}", flush=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _distribution(manifest: dict) -> dict:
    dist = manifest.get("distribution")
    return dist if isinstance(dist, dict) else {}


def release_download_url(manifest: dict) -> str | None:
    dist = _distribution(manifest)
    override = (os.environ.get("PBJ_STAFFING_EVIDENCE_DOWNLOAD_URL") or "").strip()
    if override:
        return override
    repo = str(dist.get("github_repo") or "EricGoldwein/pbj-root").strip()
    tag = str(dist.get("release_tag") or "").strip()
    asset = str(dist.get("asset_name") or seb.SQLITE_GZ_NAME).strip()
    if not tag:
        return None
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"


def verify_gzip(path: Path, manifest: dict) -> bool:
    dist = _distribution(manifest)
    want_sha = str(dist.get("sqlite_gz_sha256") or "").strip().lower()
    want_bytes = dist.get("sqlite_gz_bytes")
    if not path.is_file():
        return False
    if want_bytes is not None:
        try:
            if int(path.stat().st_size) != int(want_bytes):
                _log(f"size mismatch: {path.stat().st_size} != {want_bytes}")
                return False
        except (TypeError, ValueError):
            pass
    if want_sha:
        got = _sha256_file(path)
        if got.lower() != want_sha:
            _log(f"sha256 mismatch: {got} != {want_sha}")
            return False
    return True


def download_gzip(app_root: str | None = None, *, force: bool = False) -> int:
    root = app_root or str(REPO)
    manifest = seb.load_manifest(root, force=True)
    if not manifest:
        _log("ERROR manifest missing or invalid")
        return 1
    if str(manifest.get("distribution", {}).get("method") or "") != "github_release":
        _log("distribution.method is not github_release; skip download")
        return 0

    gz_path = Path(seb.sqlite_gzip_path(root))
    if not force and verify_gzip(gz_path, manifest):
        _log(f"OK existing gzip verified ({gz_path.name})")
        return 0

    url = release_download_url(manifest)
    if not url:
        _log("ERROR manifest missing distribution.release_tag")
        return 1

    gz_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = gz_path.with_suffix(gz_path.suffix + ".part")
    _log(f"GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "pbj320-evidence-fetch/1.0"})
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        _log(f"ERROR HTTP {exc.code} downloading release asset")
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        return 1
    except Exception as exc:
        _log(f"ERROR download failed: {exc}")
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        return 1

    if not verify_gzip(tmp, manifest):
        _log("ERROR downloaded file failed sha256/size verification")
        tmp.unlink(missing_ok=True)
        return 1

    tmp.replace(gz_path)
    _log(f"OK wrote {gz_path.name} sha256={_distribution(manifest).get('sqlite_gz_sha256', '')[:12]}…")
    return 0


def main() -> int:
    force = os.environ.get("PBJ_STAFFING_EVIDENCE_FORCE_DOWNLOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    return download_gzip(str(REPO), force=force)


if __name__ == "__main__":
    raise SystemExit(main())
