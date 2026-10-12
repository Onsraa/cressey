import pytest
import yaml

from cressey.domain.policy import Profile, ToolRule, load_policy


def write_catalogs(data, **catalogs) -> None:
    (data / "policy.yaml").write_text(yaml.safe_dump({"stuck": {"rejections": 3}}))
    (data / "catalogs").mkdir()
    for name, catalog in catalogs.items():
        (data / "catalogs" / f"{name}.yaml").write_text(yaml.safe_dump(catalog))


def test_a_tool_listed_twice_for_one_surface_is_refused(tmp_path):
    """Its kind would depend on which file came last."""
    bash = {"surface": "hook", "tools": {"Bash": {"kind": "shell", "arg": "command"}}}
    write_catalogs(tmp_path, a=bash, b=bash)
    with pytest.raises(ValueError, match=r"b.yaml lists \['Bash'\] again"):
        load_policy(tmp_path, Profile(upstreams="demo"))


def test_the_same_name_on_two_surfaces_is_two_tools(tmp_path):
    """Claude Code's CronDelete only touches its session; a company's MCP server can have a
    CronDelete of its own that deletes its payroll job."""
    cron = {"surface": "hook", "tools": {"CronDelete": {"kind": "read"}}}
    write_catalogs(tmp_path, claude=cron)
    profile = Profile(
        upstreams="demo", tools={"CronDelete": ToolRule(kind="destructive")}
    )
    tools = load_policy(tmp_path, profile).tools
    assert (tools["hook"]["CronDelete"].kind, tools["mcp"]["CronDelete"].kind) == (
        "read",
        "destructive",
    )
