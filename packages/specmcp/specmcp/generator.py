"""Builds a tool registry purely from data: the curated OpenAPI spec x the policy YAML.

No per-resource tool function is hand-written here — every ToolSpec is produced
generically from (operationId, method, path, parameters) in the OpenAPI file,
filtered and annotated (allowed_roles, masking) by the policy file. An operation
that exists in the OpenAPI file but has no policy entry is silently dropped: it
is not exposed as a tool at all, for any role.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

DEFAULT_OPENAPI_PATH = Path(__file__).resolve().parents[3] / "fhir" / "openapi" / "fhir.yaml"
DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "fhir" / "policies" / "fhir.yaml"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    method: str
    path: str
    resource: str
    description: str
    allowed_roles: list[str] = field(default_factory=list)
    mask: dict[str, list[str]] = field(default_factory=dict)
    path_params: list[str] = field(default_factory=list)
    query_params: list[str] = field(default_factory=list)
    has_body: bool = False


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_registry(
    openapi_path: Path = DEFAULT_OPENAPI_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> dict[str, ToolSpec]:
    spec = load_yaml(openapi_path)
    policy = load_yaml(policy_path)
    ops_policy: dict = policy.get("operations", {})

    registry: dict[str, ToolSpec] = {}
    for path_str, path_item in spec.get("paths", {}).items():
        for method, op in path_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            op_id = op.get("operationId")
            if not op_id or op_id not in ops_policy:
                continue

            pol = ops_policy[op_id] or {}
            params = op.get("parameters", []) or []
            path_params = [p["name"] for p in params if p.get("in") == "path"]
            query_params = [p["name"] for p in params if p.get("in") == "query"]

            registry[op_id] = ToolSpec(
                name=op_id,
                method=method.upper(),
                path=path_str,
                resource=pol.get("resource", ""),
                description=(op.get("description") or op.get("summary") or "").strip(),
                allowed_roles=list(pol.get("allowed_roles", [])),
                mask={role: list(rules.get("hide_fields", [])) for role, rules in (pol.get("mask") or {}).items()},
                path_params=path_params,
                query_params=query_params,
                has_body="requestBody" in op,
            )
    return registry
