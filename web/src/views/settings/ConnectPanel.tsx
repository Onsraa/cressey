import { Bot, Copy, Terminal } from "lucide-react";
import { useState } from "react";
import { useLive } from "@/api/live";

export function ConnectPanel() {
	const { status } = useLive();
	const [copied, setCopied] = useState("");
	const command = status
		? `claude mcp add --transport http cressey \\\n  ${location.origin}${status.mcp_path} \\\n  --header "Authorization: Bearer <clé du run>"`
		: "";

	const copy = () => {
		// Inside the promise: without a secure context, navigator.clipboard is missing.
		Promise.resolve()
			.then(() => navigator.clipboard.writeText(command))
			.then(
				() => setCopied("Copié"),
				() => setCopied("Copie refusée"),
			);
		setTimeout(() => setCopied(""), 1500);
	};

	return (
		<section aria-label="Brancher un agent" className="panel rise">
			<div className="panel-head">
				<Bot size={14} />
				BRANCHER UN AGENT
			</div>
			<div className="flex flex-col gap-4 p-5">
				<span className="text-[13.5px] leading-[1.45]">
					À lancer une fois dans le terminal de l'agent.
				</span>
				<div className="border-[1.2px] border-ink bg-paper">
					<div className="flex h-[38px] items-center justify-between gap-2.5 border-line border-b bg-surface pr-1.5 pl-3.5">
						<span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-mute-2">
							<Terminal size={12} />
							terminal de l'agent
						</span>
						<button
							type="button"
							onClick={copy}
							disabled={!status}
							data-tip="Copie la commande. Remplacez <clé du run> par la clé reçue."
							className="btn h-[30px] px-2.5 text-[13px]"
						>
							<Copy size={14} />
							{copied || "Copier"}
						</button>
					</div>
					<pre className="m-0 overflow-x-auto whitespace-pre bg-paper p-3.5 font-mono text-xs leading-[1.5]">
						{command || "…"}
					</pre>
				</div>
				<span className="text-[13px] text-mute leading-[1.45]">
					La clé du run est donnée une seule fois, à sa création (POST
					/api/runs).
				</span>
			</div>
		</section>
	);
}
