from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from internship_collectors.career_page import collect_career_page
from internship_collectors.greenhouse import collect_greenhouse
from internship_collectors.lever import collect_lever
from internship_collectors.linkedin import collect_linkedin_search
from internship_collectors.utils import utc_now_iso

COLLECTOR_BY_TYPE = {
    "greenhouse": collect_greenhouse,
    "lever": collect_lever,
    "linkedin_search": collect_linkedin_search,
    "career_page": collect_career_page,
}


def collect_source(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("enabled") is False:
        return {
            "source": source.get("source_name") or source.get("type"),
            "collected_at": utc_now_iso(),
            "jobs": [],
            "skipped": True,
        }
    source_type = str(source["type"]).strip()
    collector = COLLECTOR_BY_TYPE.get(source_type)
    if collector is None:
        raise ValueError(f"Unsupported collector type: {source_type}")
    jobs = collector(source)
    return {
        "source": str(source.get("source_name") or source_type),
        "source_type": source_type,
        "collected_at": utc_now_iso(),
        "jobs": jobs,
    }


def collect_all_sources(
    config: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    written_files: list[str] = []

    for index, source in enumerate(config.get("sources", []), start=1):
        source_name = str(source.get("source_name") or f"source_{index}")
        try:
            payload = collect_source(source)
            if payload.get("skipped"):
                results.append(payload)
                continue
            file_path = output_dir / f"{source_name}.json"
            file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written_files.append(str(file_path))
            results.append(
                {
                    "source": payload["source"],
                    "source_type": payload["source_type"],
                    "job_count": len(payload["jobs"]),
                    "file": str(file_path),
                }
            )
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            errors.append({"source": source_name, "error": str(error)})

    summary = {
        "collected_at": utc_now_iso(),
        "output_dir": str(output_dir),
        "sources": results,
        "written_files": written_files,
        "errors": errors,
        "total_jobs": sum(item.get("job_count", 0) for item in results),
    }
    summary_path = output_dir / "collection_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary
