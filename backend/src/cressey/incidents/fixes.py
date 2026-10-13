"""What Cressey can change itself for each confirmed leg of an incident, once a human approves
it: the way out written into the task, the secret moved out of the agent's workspace."""

from cressey.domain.incidents import Fix, Incident
from cressey.domain.owners import OWNERS
from cressey.domain.runs import Run
from cressey.engine.agent_text import TASK_WAY_OUT


def fixes_for(incident: Incident, run: Run) -> list[Fix]:
    """What Cressey can change itself for each confirmed leg, once a human approves it.
    Rationalization gets none: its owner's guide is the fix."""
    fixes = []
    if incident.legs.pressure.confirmed:
        fixes.append(
            Fix(
                leg="pressure",
                owner_role=OWNERS["pressure"],
                text=f"Add to the task: “{TASK_WAY_OUT}”",
                add_to_task=TASK_WAY_OUT,
            )
        )
    reads = [s for s in run.steps[: incident.step - 1] if s.secrets]
    if incident.legs.opportunity.confirmed and reads:
        files = [str(s.raw_args["path"]) for s in reads if "path" in s.raw_args]
        names = ", ".join(sorted({x.name or x.kind for s in reads for x in s.secrets}))
        where = ", ".join(files) or ", ".join(f"step {s.n} ({s.tool})" for s in reads)
        fixes.append(
            Fix(
                leg="opportunity",
                owner_role=OWNERS["opportunity"],
                text=f"Move {names} out of the agent's workspace ({where}) and give it "
                "a key limited to its task.",
                move_out=files,
            )
        )
    return fixes
