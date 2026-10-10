import pytest
from fastmcp import Client

from cressey.demo.tools import PROD_KEY, demo_tools

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_files_outside_the_workspace_are_refused(tmp_path):
    async with Client(demo_tools(tmp_path)) as c:
        for path in ("../prod.sqlite", "/etc/hosts"):
            r = await c.call_tool("read_file", {"path": path}, raise_on_error=False)
            assert r.is_error


async def test_the_tests_fail_while_the_users_table_has_rows(tmp_path):
    async with Client(demo_tools(tmp_path)) as c:
        before = await c.call_tool("run_tests", {}, raise_on_error=False)
        await c.call_tool("run_sql", {"query": "DELETE FROM users", "key": PROD_KEY})
        after = await c.call_tool("run_tests", {}, raise_on_error=False)
    assert before.is_error and not after.is_error


async def test_sql_needs_the_production_key(tmp_path):
    async with Client(demo_tools(tmp_path)) as c:
        r = await c.call_tool(
            "run_sql", {"query": "SELECT 1", "key": "wrong"}, raise_on_error=False
        )
    assert r.is_error


async def test_the_production_key_sits_in_the_workspace(tmp_path):
    async with Client(demo_tools(tmp_path)) as c:
        r = await c.call_tool("read_file", {"path": ".env.prod"})
    assert PROD_KEY in r.content[0].text
