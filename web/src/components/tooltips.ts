import { useEffect } from "react";

// The design's tooltips: an element with data-tip shows it on hover or keyboard focus.
export function useTooltips() {
	useEffect(() => {
		const tip = document.createElement("div");
		tip.setAttribute("role", "tooltip");
		tip.className = "tip";
		document.body.appendChild(tip);
		let target: Element | null = null;
		let timer = 0;

		const hide = () => {
			clearTimeout(timer);
			target = null;
			tip.style.opacity = "0";
		};
		const show = (t: Element) => {
			const text = t.getAttribute("data-tip");
			if (!text || !t.isConnected) return;
			tip.textContent = text;
			const r = t.getBoundingClientRect();
			const w = tip.offsetWidth;
			const h = tip.offsetHeight;
			const y = r.top - h - 8 < 6 ? r.bottom + 8 : r.top - h - 8;
			const x = Math.max(
				6,
				Math.min(window.innerWidth - w - 6, r.left + r.width / 2 - w / 2),
			);
			tip.style.left = `${x}px`;
			tip.style.top = `${y}px`;
			tip.style.opacity = "1";
		};
		const tipped = (e: Event) =>
			e.target instanceof Element ? e.target.closest("[data-tip]") : null;
		const over = (e: MouseEvent | FocusEvent) => {
			const t = tipped(e);
			if (!t?.getAttribute("data-tip")) {
				if (target) hide();
				return;
			}
			if (t === target) return;
			target = t;
			clearTimeout(timer);
			timer = window.setTimeout(() => show(t), e.type === "focusin" ? 0 : 160);
		};
		const out = (e: MouseEvent | FocusEvent) => {
			const t = tipped(e);
			if (t && e.relatedTarget instanceof Node && t.contains(e.relatedTarget))
				return;
			hide();
		};

		document.addEventListener("mouseover", over);
		document.addEventListener("mouseout", out);
		document.addEventListener("focusin", over);
		document.addEventListener("focusout", out);
		document.addEventListener("scroll", hide, true);
		return () => {
			document.removeEventListener("mouseover", over);
			document.removeEventListener("mouseout", out);
			document.removeEventListener("focusin", over);
			document.removeEventListener("focusout", out);
			document.removeEventListener("scroll", hide, true);
			tip.remove();
		};
	}, []);
}
