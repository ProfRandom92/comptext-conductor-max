import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


def _repo(root: Path) -> None:
    track = root / "conductor" / "tracks" / "demo"
    track.mkdir(parents=True)
    (track / "spec.md").write_text("# Spec\nRENDERER=KNI\n", encoding="utf-8")
    (track / "plan.md").write_text("- [ ] MAP-003 legacy coordinate transform\n", encoding="utf-8")
    (root / "map.py").write_text("def legacy_coordinate_transform():\n    return 12\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_real_stdio_subprocess_lists_six_tools_and_calls_search(tmp_path: Path):
    _repo(tmp_path)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "comptext_conductor_max.mcp_server"],
        env={**os.environ, "CT_CONDUCTOR_ROOT": str(tmp_path)},
    )
    async with Client(stdio_client(params)) as client:
        listed = await client.list_tools()
        assert {tool.name for tool in listed.tools} == {
            "ct_context",
            "ct_search",
            "ct_diff",
            "ct_result",
            "ct_checkpoint",
            "ct_stats",
        }
        called = await client.call_tool(
            "ct_search",
            {"query": "legacy coordinate", "max_results": 2, "max_lines": 20},
        )
        assert called.is_error is False
        assert called.structured_content is not None
        assert called.structured_content["results"][0]["path"] == "map.py"
