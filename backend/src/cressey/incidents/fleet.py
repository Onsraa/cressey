"""The signal across runs (Hugging Face / METR): each run alone looks like one hold; many
runs held for the same target outside their mandate, within a window, are the alarm (« peers
doing it »). A target is the tool and the floor's reason."""

from datetime import datetime, timedelta

from cressey.domain.incidents import FleetSignal
from cressey.domain.policy import Fleet
from cressey.store.eventlog import EventLog


class FleetWatch:
    def __init__(self, rule: Fleet, log: EventLog) -> None:
        self.rule, self.log = rule, log
        self._targets: dict[
            str, list[tuple[datetime, str]]
        ] = {}  # target -> (when, run)
        self._signals: dict[str, FleetSignal] = {}

    def count(self, target: str, run_id: str, now: datetime) -> None:
        """One more run held for this target, now: a signal once enough runs are."""
        window = timedelta(minutes=self.rule.window_minutes)
        seen = [(t, r) for t, r in self._targets.get(target, []) if now - t <= window]
        seen.append((now, run_id))
        self._targets[target] = seen
        ids = list(dict.fromkeys(r for _, r in seen))
        if len(ids) < self.rule.runs:
            return
        if target not in self._signals:
            self.log.append("fleet_signal", {"target": target, "runs": len(ids)})
        self._signals[target] = FleetSignal(
            target=target,
            runs=ids,
            first_at=seen[0][0].isoformat(),
            last_at=now.isoformat(),
        )

    def signalled(self, target: str) -> bool:
        return target in self._signals

    def signals(self) -> list[FleetSignal]:
        """The signals, the latest first."""
        return sorted(self._signals.values(), key=lambda s: s.last_at, reverse=True)
