"""
Trim the fixed Spotify OpenAPI spec to only include operations used by the MCP tools.
"""
import copy
import yaml
import sys
from pathlib import Path

# Operations (operationId) needed by the Spotify MCP tools in main.bicep
NEEDED_OPERATIONS = {
    "search",
    "create-playlist",
    "get-a-list-of-current-users-playlists",
    "get-playlists-items",
    "get-playlist",
    "get-an-album",
    "get-an-artist",
    "get-an-artists-albums",
    "get-an-artists-top-tracks",
    "get-current-users-profile",
    "get-new-releases",
    "get-playlist-cover",
    "get-an-albums-tracks",
    "reorder-or-replace-playlists-items",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def collect_refs(obj, refs: set):
    """Recursively collect all $ref values from an object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                refs.add(v)
            else:
                collect_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            collect_refs(item, refs)


def resolve_component_refs(spec: dict, refs: set) -> set:
    """Expand refs transitively within components."""
    components = spec.get("components", {})
    resolved = set()
    queue = list(refs)

    while queue:
        ref = queue.pop()
        if ref in resolved:
            continue
        resolved.add(ref)

        # "#/components/schemas/Foo" -> ["schemas", "Foo"]
        if ref.startswith("#/components/"):
            parts = ref[len("#/components/"):].split("/", 1)
            if len(parts) == 2:
                section, name = parts
                obj = components.get(section, {}).get(name)
                if obj:
                    new_refs = set()
                    collect_refs(obj, new_refs)
                    for r in new_refs:
                        if r not in resolved:
                            queue.append(r)

    return resolved


def trim_spec(input_path: Path, output_path: Path):
    with open(input_path) as f:
        spec = yaml.safe_load(f)

    # Build trimmed paths keeping only needed operations
    trimmed_paths = {}
    for path, path_item in spec.get("paths", {}).items():
        new_path_item = {}
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                # Keep non-method keys (like parameters, summary at path level)
                new_path_item[method] = operation
                continue
            if isinstance(operation, dict):
                op_id = operation.get("operationId")
                if op_id in NEEDED_OPERATIONS:
                    new_path_item[method] = operation
        if any(m in new_path_item for m in HTTP_METHODS):
            trimmed_paths[path] = new_path_item

    # Collect all $refs used by the trimmed paths
    refs: set = set()
    collect_refs(trimmed_paths, refs)

    # Transitively resolve component refs
    all_refs = resolve_component_refs(spec, refs)

    # Build trimmed components
    trimmed_components: dict = {}
    for ref in all_refs:
        if ref.startswith("#/components/"):
            parts = ref[len("#/components/"):].split("/", 1)
            if len(parts) == 2:
                section, name = parts
                obj = spec.get("components", {}).get(section, {}).get(name)
                if obj is not None:
                    trimmed_components.setdefault(section, {})[name] = copy.deepcopy(obj)

    # Keep securitySchemes wholesale (needed for auth declarations)
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    if security_schemes:
        trimmed_components["securitySchemes"] = copy.deepcopy(security_schemes)

    trimmed_spec = {
        "openapi": spec["openapi"],
        "info": spec["info"],
        "servers": spec.get("servers", []),
        "tags": spec.get("tags", []),
        "paths": trimmed_paths,
        "components": trimmed_components,
    }

    with open(output_path, "w") as f:
        yaml.dump(trimmed_spec, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    size = output_path.stat().st_size
    print(f"Trimmed spec written to {output_path} ({size:,} bytes)")
    if size > 131072:
        print(f"WARNING: Still exceeds Bicep limit of 131,072 bytes by {size - 131072:,} bytes")
    else:
        print(f"OK: Within Bicep limit (headroom: {131072 - size:,} bytes)")


if __name__ == "__main__":
    root = Path(__file__).parent.parent / "infra" / "openapi"
    input_path = root / "fixed-spotify-open-api.yml"
    output_path = root / "spotify-openapi-trimmed.yml"
    trim_spec(input_path, output_path)
