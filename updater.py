"""Periksa TrustPositif; tandai domain diblokir tanpa menyimpan daftar ke Firebase."""
import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

SOURCE_URL = os.getenv("TRUSTPOSITIF_SOURCE_URL", "https://trustpositif.komdigi.go.id/assets/db/domains_isp")
DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://panel-ai-result-default-rtdb.asia-southeast1.firebasedatabase.app")
DATA_FILE = Path(__file__).resolve().parent / "data" / "domains_isp.txt"
INTERVAL_SECONDS = 300
REQUEST_TIMEOUT = (15, 90)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def normalize_domain(value):
    """Normalisasi HTTP(S), hostname dan IDN; tolak input yang bukan domain."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or re.search(r"\s", value):
        return ""
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        if parsed.scheme.lower() not in {"http", "https"} or parsed.username or parsed.password:
            return ""
        parsed.port  # Validasi nomor port.
        host = (parsed.hostname or "").rstrip(".").lower().encode("idna").decode("ascii")
    except (ValueError, UnicodeError):
        return ""
    host = host.removeprefix("www.")
    labels = host.split(".")
    if len(host) > 253 or len(labels) < 2:
        return ""
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        return ""
    return host


def parse_blocklist(content, content_type=""):
    """Jangan menafsirkan halaman HTML/error sebagai daftar domain."""
    text = content.decode("utf-8-sig", errors="strict")
    if "html" in content_type.lower() or re.search(r"<\s*(?:!doctype|html|head|body|script)\b", text, re.I):
        raise ValueError("Sumber mengembalikan HTML, bukan daftar domain.")
    domains = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        for candidate in re.split(r"[\s,;]+", line):
            domain = normalize_domain(candidate.strip("\"'"))
            if domain:
                domains.add(domain)
    if len(domains) < 10:
        raise ValueError(f"Daftar tidak valid: hanya {len(domains)} domain terbaca.")
    return domains


def connect_firebase():
    import firebase_admin
    from firebase_admin import credentials, db
    path = os.getenv("FIREBASE_CREDENTIALS")
    if not path:
        raise RuntimeError("Atur FIREBASE_CREDENTIALS ke lokasi JSON service account di luar repository.")
    if not Path(path).is_file():
        raise FileNotFoundError("File pada FIREBASE_CREDENTIALS tidak ditemukan.")
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(credentials.Certificate(path), {"databaseURL": DATABASE_URL})
    return db.reference("domain_checks", app=app)


def download_blocklist():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.unlink(missing_ok=True)
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    logging.info("Mengunduh daftar ISP TrustPositif; ukuran sekitar 218 MB, proses dapat memerlukan beberapa menit.")
    with requests.get(SOURCE_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "TrustPositif-Domain-Checker/1.1"}) as response:
        response.raise_for_status()
        domains = parse_blocklist(response.content, response.headers.get("Content-Type", ""))
        temporary.write_bytes(response.content)
    temporary.replace(DATA_FILE)
    return domains


def get_record_domain(record):
    for field in ("link", "url", "website", "domain"):
        domain = normalize_domain(record.get(field))
        if domain:
            return domain
    return ""


def check_firebase_records(firebase_ref, blocked_domains):
    records = firebase_ref.get() or {}
    if not isinstance(records, dict):
        raise ValueError("domain_checks harus berbentuk object/map.")
    updates = {}
    count = blocked_count = 0
    for record_id, record in records.items():
        if not isinstance(record, dict):
            continue
        domain = get_record_domain(record)
        if not domain:
            continue
        count += 1
        if domain not in blocked_domains:
            continue
        blocked_count += 1
        if record.get("blocked") is True and record.get("status") == "diblokir":
            continue
        updates[f"{record_id}/blocked"] = True
        updates[f"{record_id}/status"] = "diblokir"
        updates[f"{record_id}/checked_at"] = {".sv": "timestamp"}
    if updates:
        firebase_ref.update(updates)
    logging.info("Selesai: %s domain diperiksa, %s diblokir, %s status diperbarui.", count, blocked_count, len(updates) // 3)
    return count


def cleanup_download():
    DATA_FILE.unlink(missing_ok=True)
    DATA_FILE.with_suffix(".tmp").unlink(missing_ok=True)


def run_once(firebase_ref):
    success = False
    try:
        domains = download_blocklist()
        logging.info("Daftar valid: %s domain.", len(domains))
        check_firebase_records(firebase_ref, domains)
        success = True
    except Exception:
        logging.exception("Siklus gagal; periksa koneksi atau akses Firebase.")
    finally:
        try:
            cleanup_download()
        except OSError:
            logging.exception("File unduhan belum dapat dihapus.")
            success = False
    return success


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Jalankan satu siklus; exit 1 bila gagal.")
    parser.add_argument("--validate-source", action="store_true", help="Uji sumber daftar tanpa akses Firebase.")
    parser.add_argument("--interval", type=int, default=INTERVAL_SECONDS, help="Jeda antarsiklus dalam detik (default 300).")
    args = parser.parse_args(argv)
    if args.interval < 1:
        parser.error("--interval minimal 1 detik")
    try:
        if args.validate_source:
            try:
                domains = download_blocklist()
                logging.info("Sumber berhasil divalidasi: %s domain.", len(domains))
                return 0
            finally:
                cleanup_download()
        firebase_ref = connect_firebase()
        if args.once:
            return 0 if run_once(firebase_ref) else 1
        logging.info("Pemeriksa aktif; jeda antarsiklus %s detik. Ctrl+C untuk berhenti.", args.interval)
        while True:
            run_once(firebase_ref)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logging.info("Pemeriksa dihentikan.")
        return 0
    except Exception as exc:
        logging.error("Tidak dapat menjalankan pemeriksa: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
