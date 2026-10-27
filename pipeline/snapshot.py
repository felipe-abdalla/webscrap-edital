import hashlib
import json
import subprocess
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

DATASETS_DIR = Path("datasets")

_TRACKED_LIBS = ["dateparser", "beautifulsoup4", "requests"]

def _guess_extension(content_type: str, body: bytes) -> str:
    if body[:4] == b"%PDF" or "applicaiton/pdf" in content_type:
        return ".pdf"
    if "html" in content_type:
        return ".html"
    return ".bin"

def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    
    except Exception:
        return None

def _lib_versions() -> dict:
    versions = {}
    for lib in _TRACKED_LIBS:
        try:
            versions[lib] = version(lib)
        except PackageNotFoundError:
            versions[lib] = None
    return versions

def new_run_dir(run_at: datetime) -> Path:
    run_dir = DATASETS_DIR / f"run_{run_at:%Y-%m-%dT%H-%M-%S}"
    (run_dir / "raw").mkdir(parents=True, exist_ok=False)
    return run_dir

def save_snapshot(run_dir: Path, run_at: datetime, queries: list[str], items: list[dict], config: dict) -> dict:
    """Grava os bytes de cada página em um raw/ e os metadados em manifest.json"""

    stored_items = []

    for item in items:
        raw = item["raw"]
        body = raw["body"]
        raw_file = None

        if body:
            name = hashlib.sha256(body).hexdigest() + _guess_extension(raw["content_type"], body)
            path = run_dir / "raw" / name
            if not path.exists():
                path.write_bytes(body)
            raw_file = f"raw/{name}"

        stored_items.append({
            "id": item["id"],
            "url": item["url"],
            "title": item["title"],
            "query": item["query"],
            "snippet": item["snippet"],
            "raw_file": raw_file,
            "status": raw["status"],
            "content_type": raw["content_type"],
            "final_url": raw["final_url"],
            "encoding": raw["encoding"],
            "error": raw["error"]
        })

    manifest = {
        "run_at": run_at.isoformat(),
        "git_commit": _git_commit(),
        "lib_verisons": _lib_versions(),
        "queries": queries,
        "config": config,
        "items": stored_items,
    }

    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Snapshot salvo em: {run_dir}")

    return load_snapshot(run_dir)

def load_snapshot(run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)

    with open(run_dir / "manifest.json", encoding="utf-8") as f:
        snapshot = json.load(f)

    snapshot["run_at"] = datetime.fromisoformat(snapshot["run_at"])
    snapshot["run_dir"] = run_dir

    return snapshot

def read_raw(run_dir: Path, item: dict) -> dict:
    """Reconstrói o dicionário no formado de fetch_raw a partir do disco"""

    body = (run_dir / item["raw_file"]).read_bytes() if item["raw_file"] else b""

    return {
        "status": item["status"],
        "content_type": item["content_type"],
        "final_url": item["final_url"],
        "encoding": item["encoding"],
        "body": body,
        "error": item["error"],
    }