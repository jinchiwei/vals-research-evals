"""Download and verify the hosted release; a signed URL is read from a private file.

Run on the authorized data host. Never print or persist the signed URL in reports.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import urllib.error
import urllib.request
import zipfile


PROXY_KEYS = {'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}


def load_proxy_environment(path):
    """Load only network proxy settings from an owner-only configuration file."""
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise PermissionError('Proxy environment must be private and not a symlink')
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or any(
        not isinstance(k, str) or k.lower() not in PROXY_KEYS or not isinstance(v, str)
        for k, v in data.items()
    ):
        raise ValueError('Only proxy environment keys with string values are allowed')
    return data


def safe_error_details(exc):
    """Exception text may contain credentials or signed URLs; never expose it."""
    reason = getattr(exc, 'reason', None)
    errno = getattr(reason, 'errno', None)
    code = getattr(exc, 'code', None)
    return {'error_type': type(exc).__name__,
            'error_reason_type': type(reason).__name__ if reason is not None else None,
            'error_errno': errno if isinstance(errno, int) else None,
            'http_status': code if isinstance(code, int) else None}


def download(destination, url_file, resume=False, proxy_env_file=None):
    os.umask(0o077)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    url = url_file.read_text().strip()
    archive = destination / "pcnsl-dataset_v1.0.zip"
    partial = destination / "pcnsl-dataset_v1.0.zip.part"
    status_path = destination / "download_status.json"
    state = {"source": "https://s3-us-west-1.amazonaws.com/ucsf-dmi/pcnsl-dataset_v1.0.zip",
             "doi": "10.58078/C2RP4V", "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    def status(phase, **fields):
        state.update(phase=phase, updated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields)
        temporary = status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(status_path)
    try:
        if proxy_env_file is not None:
            os.environ.update(load_proxy_environment(proxy_env_file))
            urllib.request.install_opener(urllib.request.build_opener())
            state['explicit_proxy_environment_loaded'] = True
        if archive.exists() or (partial.exists() and not resume):
            raise FileExistsError("Use a fresh download directory")
        expected = None
        etag = None
        if partial.exists():
            previous = json.loads(status_path.read_text())
            if previous.get("source") != state["source"] or not previous.get("etag"):
                raise ValueError("Cannot resume without matching source metadata")
            expected, etag = previous["expected_bytes"], previous["etag"]
            state.update(previous)
        status("connecting")
        for attempt in range(6):
            start = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={start}-"} if start else {}
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
                    if start and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-")):
                        raise ValueError("Server did not honor resumption range")
                    current_etag = response.headers.get("ETag")
                    if etag is not None and etag != current_etag:
                        raise ValueError("Source changed during download")
                    etag = current_etag
                    total = int(response.headers["Content-Length"]) + start
                    if expected is not None and total != expected:
                        raise ValueError("Source size changed during download")
                    expected = total
                    if shutil.disk_usage(destination).free < expected - start + 2 * 2**30:
                        raise OSError("Insufficient free space")
                    status("downloading", expected_bytes=expected, downloaded_bytes=start,
                           etag=etag, last_modified=response.headers.get("Last-Modified"), attempt=attempt + 1,
                           error_type=None, error_reason_type=None, error_errno=None, http_status=None)
                    last = time.monotonic()
                    with partial.open("ab" if start else "wb") as output:
                        while True:
                            block = response.read(8 * 2**20)
                            if not block:
                                break
                            output.write(block)
                            start += len(block)
                            if time.monotonic() - last >= 10:
                                output.flush()
                                status("downloading", downloaded_bytes=start)
                                last = time.monotonic()
                if partial.stat().st_size != expected:
                    raise EOFError("Incomplete response")
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError, EOFError, http.client.IncompleteRead) as exc:
                status("retrying", attempt=attempt + 1,
                       downloaded_bytes=partial.stat().st_size if partial.exists() else 0,
                       **safe_error_details(exc))
                if attempt == 5:
                    raise
                time.sleep(min(30, 2 ** attempt))
        status("hashing", downloaded_bytes=partial.stat().st_size)
        digest = hashlib.sha256()
        with partial.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 2**20), b""):
                digest.update(block)
        partial.replace(archive)
        state["sha256"] = digest.hexdigest()
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            unpacked = sum(m.file_size for m in members)
            if unpacked > 100 * 2**30 or shutil.disk_usage(destination).free < unpacked + 2 * 2**30:
                raise OSError("Archive extraction exceeds space limit")
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Unsafe archive entry")
            target = destination / "extracted.partial"
            target.mkdir(mode=0o700)
            status("extracting_and_checking_crc", archive_files=len(members), uncompressed_bytes=unpacked)
            files = 0
            for member in members:
                path = target / member.filename
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True, mode=0o700)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with package.open(member) as source, path.open("wb") as output:
                    shutil.copyfileobj(source, output, length=8 * 2**20)
                files += 1
                if files % 250 == 0:
                    status("extracting_and_checking_crc", files_extracted=files)
            target.rename(destination / "extracted")
        status("complete", files_extracted=files, zip_crc_verified=True)
        url_file.unlink()
    except Exception as exc:
        # Exception strings can contain the presigned URL. Record only its type/status.
        status("failed", **safe_error_details(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--proxy-env-file", type=Path)
    args = parser.parse_args()
    download(args.destination, args.url_file, args.resume, args.proxy_env_file)
