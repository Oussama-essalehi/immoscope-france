"""Validate the Power BI project files (PBIP / PBIR / PBISM) against Microsoft's JSON schemas.

Every JSON file of ``powerbi/`` declares its ``$schema`` URL. The schemas (and
the schemas they reference) are downloaded once into ``powerbi/.schema_cache/``
(git-ignored), then each file is validated with ``jsonschema``. The TMDL files
are checked for basic structural consistency (tables referenced by the model,
relationships pointing to existing columns, measures referenced by visuals).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import requests
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from src.settings import PROJECT_ROOT, setup_logging

logger = logging.getLogger("validate_powerbi")

PBI_DIR = PROJECT_ROOT / "powerbi"
CACHE_DIR = PBI_DIR / ".schema_cache"
SCHEMA_ROOT = "https://developer.microsoft.com/json-schemas/"


def cached_schema(url: str) -> dict:
    """Return a schema document, downloading it into the cache on first use."""
    url = urldefrag(url).url
    if not url.startswith(SCHEMA_ROOT):
        raise ValueError(f"Unexpected schema location: {url}")
    path = CACHE_DIR / url.removeprefix(SCHEMA_ROOT)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def collect_refs(node: object, base: str, seen: set[str]) -> None:
    """Recursively download every schema reachable through relative ``$ref``."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            target = urldefrag(urljoin(base, ref)).url
            if target not in seen:
                seen.add(target)
                collect_refs(cached_schema(target), target, seen)
        for value in node.values():
            collect_refs(value, base, seen)
    elif isinstance(node, list):
        for value in node:
            collect_refs(value, base, seen)


def build_registry(urls: set[str]) -> Registry:
    """Registry with every schema reachable from ``urls`` (for offline $ref resolution)."""
    seen = set(urls)
    for url in urls:
        collect_refs(cached_schema(url), url, seen)
    resources = [(u, Resource.from_contents(cached_schema(u), default_specification=DRAFT7)) for u in seen]
    return Registry().with_resources(resources)


def validate_json_files() -> int:
    """Validate every JSON file that declares a ``$schema``; return the error count."""
    files = [
        p for p in PBI_DIR.rglob("*")
        if p.suffix in {".json", ".pbir", ".pbism", ".pbip"} and ".schema_cache" not in p.parts
    ]
    documents = {p: json.loads(p.read_text(encoding="utf-8")) for p in files}
    with_schema = {p: d for p, d in documents.items() if isinstance(d, dict) and "$schema" in d}
    registry = build_registry({d["$schema"] for d in with_schema.values()})

    errors = 0
    for path, doc in sorted(with_schema.items()):
        schema = cached_schema(doc["$schema"])
        validator = Draft7Validator(schema, registry=registry)
        problems = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        rel = path.relative_to(PROJECT_ROOT)
        if problems:
            errors += len(problems)
            for problem in problems:
                logger.error("%s: %s at /%s", rel, problem.message, "/".join(map(str, problem.path)))
        else:
            logger.info("OK  %s", rel)
    skipped = sorted(set(documents) - set(with_schema))
    for path in skipped:
        logger.info("--  %s (no $schema: theme or resource file)", path.relative_to(PROJECT_ROOT))
    return errors


# --------------------------------------------------------------------------- #
# TMDL consistency checks
# --------------------------------------------------------------------------- #
def tmdl_objects(model_dir: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return {table: columns} and {table: measures} declared in the TMDL tables."""
    columns: dict[str, set[str]] = {}
    measures: dict[str, set[str]] = {}
    for path in sorted((model_dir / "tables").glob("*.tmdl")):
        text = path.read_text(encoding="utf-8")
        table = unquote(re.search(r"^table (.+)$", text, re.M).group(1))
        columns[table] = {unquote(m) for m in re.findall(r"^\tcolumn (.+?)(?: =.*)?$", text, re.M)}
        measures[table] = {unquote(m) for m in re.findall(r"^\tmeasure (.+?) =", text, re.M)}
    return columns, measures


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") and name.endswith("'") else name


def validate_tmdl(model_dir: Path, report_dir: Path) -> int:
    """Cross-check model.tmdl refs, relationships and every field used by visuals."""
    errors = 0
    columns, measures = tmdl_objects(model_dir)
    model = (model_dir / "model.tmdl").read_text(encoding="utf-8")
    for ref in re.findall(r"^ref table (.+)$", model, re.M):
        if unquote(ref) not in columns:
            logger.error("model.tmdl references missing table %s", ref)
            errors += 1
    rels = (model_dir / "relationships.tmdl").read_text(encoding="utf-8")
    for side, ref in re.findall(r"(fromColumn|toColumn): (.+)", rels):
        table, column = ref.rsplit(".", 1)
        if unquote(column) not in columns.get(unquote(table), set()):
            logger.error("relationship %s %s points to a missing column", side, ref)
            errors += 1

    for visual in sorted(report_dir.rglob("visual.json")) + sorted(report_dir.rglob("page.json")):
        text = visual.read_text(encoding="utf-8")
        for kind, entity, prop in re.findall(
            r'"(Column|Measure)":\s*\{\s*"Expression":\s*\{\s*"SourceRef":\s*\{\s*"Entity":\s*"([^"]+)"\s*\}\s*\},\s*"Property":\s*"([^"]+)"',
            text,
        ):
            known = columns if kind == "Column" else measures
            if prop not in known.get(entity, set()):
                logger.error("%s uses unknown %s %s[%s]", visual.relative_to(PROJECT_ROOT), kind.lower(), entity, prop)
                errors += 1
    if not errors:
        n_cols = sum(map(len, columns.values()))
        n_meas = sum(map(len, measures.values()))
        logger.info("TMDL OK: %d tables, %d columns, %d measures; every visual field exists", len(columns), n_cols, n_meas)
    return errors


def run() -> None:
    errors = validate_json_files()
    errors += validate_tmdl(
        PBI_DIR / "DVF_Analyse.SemanticModel" / "definition", PBI_DIR / "DVF_Analyse.Report" / "definition"
    )
    if errors:
        raise SystemExit(f"{errors} Power BI validation error(s)")
    logger.info("Power BI project valid")


if __name__ == "__main__":
    setup_logging()
    run()
