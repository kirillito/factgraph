"""Source adapters turn content files into beats.

Each adapter is ``adapter(entry: dict, root: Path, config: dict) -> (beats, findings)``,
where ``entry`` is one ``[[sources.<name>]]`` table from factgraph.toml.
"""

from .json_data import load_json_source

ADAPTERS = {
    "json": load_json_source,
}
