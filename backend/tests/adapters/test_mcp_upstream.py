"""Cressey fronts the MCP servers its profile names, in the format MCP clients use
({"mcpServers": ...}): the calls reach the real server, decided as any other."""

import pytest
import yaml
from fastmcp import FastMCP

from cressey.app import create_app
from cressey.demo.server import serve
from cressey.settings import DEMO_PROFILE, Settings
from cressey.testing import ADMIN, QuietJudge, agent, api, fake_guide

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def notes_server() -> FastMCP:
    """A company's own MCP server: notes it can read and delete."""
    notes = FastMCP("notes")
    kept = {"q3": "Close the books on the 30th."}

    @notes.tool
    def read_note(name: str) -> str:
        return kept[name]

    @notes.tool
    def delete_note(name: str) -> str:
        kept.pop(name)
        return "deleted"

    return notes


async def test_cressey_fronts_the_mcp_server_its_profile_names(tmp_path):
    with serve(notes_server().http_app(path="/mcp")) as upstream:
        profile = tmp_path / "profile.yaml"
        servers = {"mcpServers": {"notes": {"url": f"{upstream}/mcp"}}}
        catalog = {
            "read_note": {"kind": "read"},
            "delete_note": {"kind": "destructive"},
        }
        profile.write_text(yaml.safe_dump({"upstreams": servers, "tools": catalog}))
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
            run = (
                await api(base, "POST", "/api/runs", json={"task": "tidy notes"})
            ).json()
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


def test_a_replay_fronts_the_demo_tools_whatever_the_profile(tmp_path):
    """« Rejouer ×5 » plays the demo's sessions: never against a company's servers."""
    profile = tmp_path / "profile.yaml"
    servers = {"mcpServers": {"payments": {"url": "http://127.0.0.1:9/mcp"}}}
    profile.write_text(yaml.safe_dump({"upstreams": servers}))
    settings = Settings(_env_file=None, profile=profile, admin_token=ADMIN)
    app = create_app(settings, make_guide=fake_guide, judge=QuietJudge())
    replayed = app.state.replay.make_app(tmp_path / "replay")
    assert replayed.state.settings.profile == DEMO_PROFILE
