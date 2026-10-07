"""Policy-controlled, audited tool dispatch over the FHIR REST API.

This is the callable core that a Phase 3 LangGraph node (or an MCP stdio
transport, added when there's an actual MCP client to talk to) wraps. Building
that transport now, with no consumer yet, would be speculative — this module
is what contract tests exercise directly.
"""

from pathlib import Path
from typing import Any

import psycopg
import trustcore

from specmcp import mask
from specmcp.fhir_client import execute as fhir_execute
from specmcp.generator import DEFAULT_OPENAPI_PATH, DEFAULT_POLICY_PATH, ToolSpec, build_registry


class PolicyDenied(Exception):
    def __init__(self, tool_name: str, role: str, reason: str):
        super().__init__(f"tool '{tool_name}' denied for role '{role}': {reason}")
        self.tool_name = tool_name
        self.role = role
        self.reason = reason


class SpecMCPServer:
    def __init__(
        self,
        fhir_base_url: str,
        openapi_path: Path = DEFAULT_OPENAPI_PATH,
        policy_path: Path = DEFAULT_POLICY_PATH,
    ):
        self.fhir_base_url = fhir_base_url
        self.registry: dict[str, ToolSpec] = build_registry(openapi_path, policy_path)

    def list_tools(self, role: str) -> list[ToolSpec]:
        """Tools reachable by this role. A tool a role can't use isn't listed at all."""
        return [t for t in self.registry.values() if role in t.allowed_roles]

    def call(
        self,
        tool_name: str,
        params: dict[str, Any],
        actor: str,
        role: str,
        conn: psycopg.Connection | None = None,
    ) -> dict[str, Any]:
        tool = self.registry.get(tool_name)

        if tool is None:
            trustcore.record(
                actor=actor,
                actor_role=role,
                action="tool_call",
                resource_type=tool_name,
                resource_id=params.get("id"),
                result="deny",
                reason="unknown tool",
                conn=conn,
            )
            raise PolicyDenied(tool_name, role, "unknown tool")

        if role not in tool.allowed_roles:
            trustcore.record(
                actor=actor,
                actor_role=role,
                action="tool_call",
                resource_type=tool.resource,
                resource_id=params.get("id"),
                result="deny",
                reason=f"role '{role}' not permitted for '{tool_name}'",
                conn=conn,
            )
            raise PolicyDenied(tool_name, role, f"role '{role}' not permitted")

        try:
            result = fhir_execute(self.fhir_base_url, tool, params)
        except Exception as exc:
            trustcore.record(
                actor=actor,
                actor_role=role,
                action="tool_call",
                resource_type=tool.resource,
                resource_id=params.get("id"),
                result="error",
                reason=str(exc),
                conn=conn,
            )
            raise

        hide_fields = tool.mask.get(role, [])
        if hide_fields:
            result = mask.apply_mask(result, hide_fields)

        trustcore.record(
            actor=actor,
            actor_role=role,
            action="tool_call",
            resource_type=tool.resource,
            resource_id=params.get("id"),
            result="allow",
            reason=None,
            conn=conn,
        )
        return result
