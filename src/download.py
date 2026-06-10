"""Download the keyless data backbone: USPTO PTMT technology-class-by-MSA
reports, preserved on the Internet Archive Wayback Machine.

The live USPTO pages (…/taf/cls_cbsa/{cls}cbsa_gd.htm) were retired during the
2026 migration to data.uspto.gov, but the Wayback Machine has captures. We
resolve the closest snapshot via the availability API and download the raw
("id_") capture so the HTML is the original SAS-generated table, free of the
Wayback toolbar injection.

Usage:
    py src/download.py            # download all configured PTMT classes
    py src/download.py 244        # just the core aerospace class
"""

from __future__ import annotations

import sys
import time

import requests

import config as C

HEADERS = {"User-Agent": "aerospace-atlas/1.0 (research; contact via project)"}


def _url_variants(live_url: str) -> list[str]:
    """The Wayback availability index is picky about the exact URL string, so
    try several equivalent spellings (with/without scheme and www)."""
    no_scheme = live_url.split("://", 1)[-1]          # www.uspto.gov/...
    bare = no_scheme[4:] if no_scheme.startswith("www.") else no_scheme
    return [live_url, no_scheme, bare, f"https://{bare}"]


def _wayback_raw_url(live_url: str) -> str | None:
    """Resolve the closest Wayback snapshot and return its raw (id_) capture URL."""
    for variant in _url_variants(live_url):
        api = C.WAYBACK_AVAILABLE_API.format(url=variant)
        try:
            r = requests.get(api, headers=HEADERS, timeout=60)
            r.raise_for_status()
            snap = r.json().get("archived_snapshots", {}).get("closest")
        except Exception:  # noqa: BLE001 - try next variant
            continue
        if snap and snap.get("available"):
            # snap["url"] = http://web.archive.org/web/<ts>/<orig>; insert "id_"
            # after the timestamp to fetch the raw original capture.
            ts = snap["timestamp"]
            return snap["url"].replace(f"/web/{ts}/", f"/web/{ts}id_/", 1)
    return None


def download_ptmt_class(cls: str, *, force: bool = False) -> bool:
    """Fetch one PTMT technology-class report to data/raw. Returns True on success."""
    dst = C.PTMT_HTML(cls)
    if dst.exists() and not force:
        print(f"[skip] class {cls} already present: {dst.name} "
              f"({dst.stat().st_size:,} bytes)")
        return True

    live = C.PTMT_LIVE_URL.format(cls=cls)
    raw = _wayback_raw_url(live)
    if raw is None:
        print(f"[miss] no Wayback snapshot for class {cls} ({live})")
        return False

    print(f"[get ] class {cls}: {raw}")
    r = requests.get(raw, headers=HEADERS, timeout=120)
    r.raise_for_status()
    if "<table" not in r.text.lower():
        print(f"[warn] class {cls}: response has no <table> (len={len(r.text)})")
        return False
    dst.write_text(r.text, encoding="utf-8")
    print(f"[ok  ] class {cls} -> {dst.name} ({dst.stat().st_size:,} bytes)")
    return True


def main(argv: list[str]) -> int:
    classes = argv[1:] if len(argv) > 1 else list(C.PTMT_CLASSES.keys())
    ok = 0
    for cls in classes:
        try:
            if download_ptmt_class(cls):
                ok += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"[err ] class {cls}: {exc}")
        time.sleep(1)  # be polite to the Wayback API
    print(f"\nDone: {ok}/{len(classes)} classes available in {C.RAW}")
    # The core class is required; others are best-effort context.
    core_ok = C.PTMT_HTML(C.PTMT_CORE_CLASS).exists()
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
