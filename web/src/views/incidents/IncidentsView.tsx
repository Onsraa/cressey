import { useLive } from "@/api/live";
import { Detail } from "./Detail";
import { Queue } from "./Queue";

export function IncidentsView() {
	const { incidents, focus } = useLive();
	const selected =
		incidents.find((i) => i.id === focus.incident) ?? incidents[0];
	return (
		<div className="@container flex min-h-0 flex-1 flex-col px-7 pt-6 pb-7">
			<div className="grid min-h-[1212px] flex-1 grid-cols-1 grid-rows-[300px_900px] gap-4 @min-[820px]:min-h-[560px] @min-[820px]:grid-cols-[minmax(260px,320px)_minmax(0,1fr)] @min-[820px]:grid-rows-[minmax(0,1fr)]">
				<Queue selected={selected?.id} />
				<section aria-label="Détail de l'incident" className="panel rise">
					{selected ? (
						<Detail incident={selected} />
					) : (
						<p className="p-6 font-mono text-[13px] text-mute">
							Aucun incident ouvert.
						</p>
					)}
				</section>
			</div>
		</div>
	);
}
