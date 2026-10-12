import pytest
import yaml

from cressey.domain.policy import Profile, ToolRule, load_policy


def test_a_tool_two_files_list_is_refused(tmp_path):
    """Its kind would depend on which file came last."""
    (tmp_path / "policy.yaml").write_text(yaml.safe_dump({"stuck": {"rejections": 3}}))
    (tmp_path / "catalogs").mkdir()
    catalog = {"tools": {"Bash": {"kind": "shell", "arg": "command"}}}
    (tmp_path / "catalogs" / "claude-code.yaml").write_text(yaml.safe_dump(catalog))
    profile = Profile(upstreams="demo", tools={"Bash": ToolRule(kind="read")})
    with pytest.raises(ValueError, match=r"claude-code.yaml lists \['Bash'\] again"):
        load_policy(tmp_path, profile)
