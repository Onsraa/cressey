"""Cressey fronts the MCP servers its profile names, in the format MCP clients use
({"mcpServers": ...}): the calls reach the real server, decided as any other. Nothing else of
the server passes, and nothing of the agent's reaches it."""

import contextlib
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.dependencies import get_http_headers
from mcp.shared.exceptions import MCPError

from cressey.adapters.mcp import MCP_PATH
from cressey.app import create_app
from cressey.demo.server import serve
from cressey.engine.agent_text import UNKNOWN_KEY
from cressey.settings import DEMO_PROFILE, Settings
from cressey.testing import ADMIN, QuietJudge, agent, api, fake_guide, serving

pytestmark = pytest.mark.anyio
PAYROLL = "payroll://2026-10"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def notes_server() -> FastMCP:
    """A company's own MCP server: notes it can read and delete, its payroll, a prompt."""
    notes = FastMCP("notes")
    kept = {"q3": "Close the books on the 30th."}

    @notes.tool
    def read_note(name: str) -> str:
        return kept[name]

    @notes.tool
    def delete_note(name: str) -> str:
        kept.pop(name)
        return "deleted"

    @notes.tool
    def whoami() -> str:
        """The credential the caller sent."""
        return get_http_headers(include={"authorization"}).get("authorization", "none")

    @notes.resource(PAYROLL)
    def payroll() -> str:
        return "IBAN FR76 3000 1007 9412 3456 7890 185, salary 4,200"

    @notes.prompt
    def close_books() -> str:
        return "Close the books."

    return notes


@contextlib.contextmanager
def fronting(tmp_path: Path) -> Generator[str]:
    """A Cressey whose profile names the notes server."""
    with serve(notes_server().http_app(path="/mcp")) as upstream:
        profile = tmp_path / "profile.yaml"
        servers = {"mcpServers": {"notes": {"url": f"{upstream}/mcp"}}}
        tools = {
            "read_note": {"kind": "read"},
            "delete_note": {"kind": "destructive"},
            "whoami": {"kind": "read"},
        }
        profile.write_text(yaml.safe_dump({"upstreams": servers, "tools": tools}))
        settings = Settings(
            _env_file=None,
            openai_api_key=None,
            typesafe_api_key=None,
            profile=profile,
            hold_timeout=0.3,
            admin_token=ADMIN,
            state_dir=None,
        )
        app = create_app(settings, make_guide=fake_guide, judge=QuietJudge())
        with serve(app) as base:
            yield base


async def new_run(base: str) -> dict:
    return (await api(base, "POST", "/api/runs", json={"task": "tidy notes"})).json()


async def test_cressey_fronts_the_mcp_server_its_profile_names(tmp_path):
    with fronting(tmp_path) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            read = await a.call_tool("read_note", {"name": "q3"})
            deleted = await a.call_tool(
                "delete_note", {"name": "q3"}, raise_on_error=False
            )
        steps = (await api(base, "GET", f"/api/runs/{run['id']}")).json()["steps"]
    assert read.content[0].text == "Close the books on the 30th."
    assert deleted.is_error
    assert [(s["tool"], s["status"], s["reason"]) for s in steps] == [
        ("read_note", "allowed", None),
        ("delete_note", "expired", "irreversible action"),
    ]


async def test_without_a_run_key_nothing_of_the_server_passes(tmp_path):
    with fronting(tmp_path) as base:
        async with Client(StreamableHttpTransport(base + MCP_PATH)) as a:
            asks = (
                a.list_tools,
                a.list_resources,
                a.list_resource_templates,
                a.list_prompts,
                lambda: a.read_resource(PAYROLL),
                lambda: a.get_prompt("close_books"),
            )
            for ask in asks:
                with pytest.raises(MCPError, match=UNKNOWN_KEY):
                    await ask()
            refused = await a.call_tool(
                "read_note", {"name": "q3"}, raise_on_error=False
            )
        runs = (await api(base, "GET", "/api/runs")).json()
    assert refused.is_error and refused.content[0].text == UNKNOWN_KEY
    assert runs == []


async def test_a_run_key_reaches_the_tools_and_nothing_else(tmp_path):
    """Reading a resource or a prompt would be an act Cressey neither decides nor records."""
    with fronting(tmp_path) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            tools = sorted(t.name for t in await a.list_tools())
            listed = (
                await a.list_resources(),
                await a.list_resource_templates(),
                await a.list_prompts(),
            )
            with pytest.raises(MCPError):
                await a.read_resource(PAYROLL)
            with pytest.raises(MCPError):
                await a.get_prompt("close_books")
    assert tools == ["delete_note", "read_note", "whoami"]
    assert listed == ([], [], [])


async def test_the_server_never_gets_the_agents_key(tmp_path):
    with fronting(tmp_path) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            seen = await a.call_tool("whoami", {})
    assert seen.content[0].text == "none"


def test_a_replay_fronts_the_demo_tools_whatever_the_profile(tmp_path):
    """« Rejouer ×5 » plays the demo's sessions: never against a company's servers."""
    profile = tmp_path / "profile.yaml"
    servers = {"mcpServers": {"payments": {"url": "http://127.0.0.1:9/mcp"}}}
    profile.write_text(yaml.safe_dump({"upstreams": servers}))
    settings = Settings(_env_file=None, profile=profile, admin_token=ADMIN)
    app = create_app(settings, make_guide=fake_guide, judge=QuietJudge())
    replayed = app.state.replay.make_app(tmp_path / "replay")
    assert replayed.state.settings.profile == DEMO_PROFILE


async def test_what_plays_the_demo_fronts_its_tools_whatever_the_environment_names(
    tmp_path, monkeypatch
):
    """The evals, the stage and the tests play the demo's sessions (a DELETE FROM users
    among them): a profile set for a company never sends them to its servers."""
    profile = tmp_path / "profile.yaml"
    servers = {"mcpServers": {"payments": {"url": "http://127.0.0.1:9/mcp"}}}
    profile.write_text(yaml.safe_dump({"upstreams": servers}))
    monkeypatch.setenv("CRESSEY_PROFILE", str(profile))
    with serving(tmp_path / "demo", hold_timeout=0.3) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            tools = {t.name for t in await a.list_tools()}
    assert {"read_file", "run_sql"} <= tools
