"""Load a factgraph.toml into a Project: declarations, goals, allow-lists and adapters."""

from __future__ import annotations

import tomllib
from pathlib import Path

from . import jsonloc
from .adapters import ADAPTERS
from .model import Fact, Finding, Goal, Project, Source
from .syntax import SyntaxProblem, parse_condition

FACT_TYPES = {"bool": bool, "int": int, "string": str}


class ConfigError(Exception):
    pass


def load_project(config_path: str | Path) -> Project:
    config_path = Path(config_path)
    try:
        with open(config_path, "rb") as fh:
            cfg = tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {config_path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path}: {exc}") from None

    root = config_path.parent
    cfg_name = config_path.name
    project = Project(root=str(root))

    facts_file = cfg.get("project", {}).get("facts_file")
    if facts_file:
        _load_facts_file(project, root, facts_file)
    for fact_id, decl in cfg.get("facts", {}).items():
        _declare(project, fact_id, decl, Source(cfg_name))
    project.aliases.update(cfg.get("aliases", {}))

    for goal_id, decl in cfg.get("goals", {}).items():
        try:
            cond = parse_condition(decl.get("requires"), cfg_name)
        except SyntaxProblem as exc:
            project.load_findings.append(Finding("config", f"goal '{goal_id}': {exc}", Source(cfg_name)))
            continue
        project.goals.append(Goal(goal_id, cond, dict(decl.get("tags", {})), Source(cfg_name)))

    check_cfg = cfg.get("check", {})
    project.write_only_allow = list(check_cfg.get("write_only_allow", []))
    if "self_gated_kinds" in check_cfg:
        project.self_gated_kinds = list(check_cfg["self_gated_kinds"])

    for adapter_name, entries in cfg.get("sources", {}).items():
        adapter = ADAPTERS.get(adapter_name)
        if adapter is None:
            raise ConfigError(f"{cfg_name}: unknown source adapter '{adapter_name}' (known: {', '.join(ADAPTERS)})")
        for entry in entries if isinstance(entries, list) else [entries]:
            beats, findings = adapter(entry, root, cfg)
            project.beats.extend(beats)
            project.load_findings.extend(findings)
    return project


def _load_facts_file(project: Project, root: Path, rel: str) -> None:
    path = root / rel
    try:
        data = jsonloc.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"facts file not found: {rel}") from None
    except jsonloc.JSONLocError as exc:
        raise ConfigError(f"{rel}:{exc.line}: invalid JSON") from None
    for fact_id, decl in data.get("facts", {}).items():
        _declare(project, fact_id, decl, Source(rel, jsonloc.line_of(decl)))
    project.aliases.update({str(k): str(v) for k, v in data.get("aliases", {}).items()})


def _declare(project: Project, fact_id: str, decl: dict, source: Source) -> None:
    fact_type = decl.get("type", "bool")
    if fact_type not in FACT_TYPES:
        project.load_findings.append(
            Finding("config", f"fact '{fact_id}' has unknown type '{fact_type}' (bool, int, string)", source)
        )
        fact_type = "bool"
    values = decl.get("values")
    project.facts[fact_id] = Fact(
        fact_id,
        fact_type,
        _plain(decl.get("initial")),
        [_plain(v) for v in values] if values is not None else None,
        source,
    )


def _plain(value):
    return str(value) if isinstance(value, str) else value
