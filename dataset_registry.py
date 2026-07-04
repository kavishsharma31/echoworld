from __future__ import annotations

import json
from pathlib import Path


DATASET_REGISTRY_FILE = Path(".echoworld_dataset_registry.json")


def _load_dataset_registry() -> dict[str, int]:
    if not DATASET_REGISTRY_FILE.exists():
        return {}

    try:
        data = json.loads(DATASET_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}

    registry: dict[str, int] = {}
    for npc_key, version in data.items():
        if (
            isinstance(npc_key, str)
            and isinstance(version, int)
            and not isinstance(version, bool)
            and version >= 1
        ):
            registry[npc_key] = version
    return registry


def _save_dataset_registry(registry: dict[str, int]) -> None:
    temporary_file = DATASET_REGISTRY_FILE.with_suffix(
        DATASET_REGISTRY_FILE.suffix + ".tmp"
    )
    temporary_file.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(DATASET_REGISTRY_FILE)


def get_dataset_name(npc_key: str, base_dataset: str) -> str:
    version = _load_dataset_registry().get(npc_key, 1)
    if version == 1:
        return base_dataset
    return f"{base_dataset}_v{version}"


def increment_dataset_version(npc_key: str) -> int:
    registry = _load_dataset_registry()
    version = registry.get(npc_key, 1) + 1
    registry[npc_key] = version
    _save_dataset_registry(registry)
    return version


def reset_dataset_registry() -> None:
    DATASET_REGISTRY_FILE.unlink(missing_ok=True)
