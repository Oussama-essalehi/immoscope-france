"""Download the geolocated DVF files (one gzip CSV per year and department).

Source: "Demandes de valeurs foncières géolocalisées" (Etalab, from DGFiP data)
https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

from src.settings import load_config, project_path, setup_logging

logger = logging.getLogger("download")


def available_years(base_url: str, timeout: int) -> list[int]:
    """List the yearly folders published under ``base_url`` (HTML directory index)."""
    response = requests.get(f"{base_url}/", timeout=timeout)
    response.raise_for_status()
    years = sorted({int(y) for y in re.findall(r'href="[^"]*?/(20\d{2})/"', response.text)})
    if not years:
        raise RuntimeError(f"No yearly folder found at {base_url}/")
    return years


def resolve_years(cfg: dict) -> list[int]:
    """Return the configured years, or every published year when set to ``auto``."""
    years = cfg["scope"]["years"]
    if years == "auto":
        source = cfg["data_source"]
        return available_years(source["base_url"], source["timeout_seconds"])
    return [int(y) for y in years]


def download_file(url: str, target: Path, timeout: int) -> None:
    """Stream ``url`` to ``target`` atomically (temporary file, then rename)."""
    tmp = target.with_suffix(target.suffix + ".part")
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(tmp, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    tmp.replace(target)


def raw_file_path(year: int, department: str) -> Path:
    """Local path of the raw file for one year and one department."""
    return project_path("raw") / f"dvf_{year}_{department}.csv.gz"


def run(force: bool = False) -> list[Path]:
    """Download every (year, department) file in scope; skip files already present."""
    cfg = load_config()
    source = cfg["data_source"]
    years = resolve_years(cfg)
    departments = cfg["scope"]["departments"]
    logger.info("Years in scope: %s | departments: %s", years, departments)

    paths: list[Path] = []
    for year in years:
        for department in departments:
            target = raw_file_path(year, department)
            paths.append(target)
            if target.exists() and not force:
                logger.info("Already present: %s", target.name)
                continue
            url = source["file_pattern"].format(
                base_url=source["base_url"], year=year, department=department
            )
            logger.info("Downloading %s", url)
            download_file(url, target, source["timeout_seconds"])
            logger.info("Saved %s (%.1f MB)", target.name, target.stat().st_size / 1e6)
    return paths


if __name__ == "__main__":
    setup_logging()
    run()
