import gsap from "gsap";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

// The design's motion, with GSAP as its prototype runs it. Reduced motion: nothing moves.
export const still = () =>
	window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// animIn: the blocks of a view, a tab or a pane rise into place one after the other.
export function animIn(
	root: ParentNode | null | undefined,
	sel = "[data-anim]",
) {
	if (!root || still()) return;
	const els = root.querySelectorAll(sel);
	if (els.length)
		gsap.fromTo(
			els,
			{ y: 10, opacity: 0 },
			{
				y: 0,
				opacity: 1,
				duration: 0.34,
				stagger: 0.04,
				ease: "power3.out",
				clearProps: "transform,opacity",
			},
		);
}

// Runs fn after `key` changes, before the paint, but not on mount: the view's own
// entrance covers the mount.
export function useOnChange(key: unknown, fn: () => void) {
	const last = useRef(key);
	useLayoutEffect(() => {
		if (Object.is(last.current, key)) return;
		last.current = key;
		fn();
	});
}

// A shown number glides to its new value in 0.7 s (the design's tweenGauges).
export function useGlide(p: number, o: number, r: number) {
	const box = useRef({ p, o, r });
	const [shown, setShown] = useState(box.current);
	useEffect(() => {
		const b = box.current;
		if (b.p === p && b.o === o && b.r === r) return;
		if (still()) {
			Object.assign(b, { p, o, r });
			setShown({ ...b });
			return;
		}
		const tw = gsap.to(b, {
			p,
			o,
			r,
			duration: 0.7,
			ease: "power2.out",
			overwrite: true,
			onUpdate: () => setShown({ ...b }),
		});
		return () => {
			tw.kill();
		};
	}, [p, o, r]);
	return shown;
}

// A new trace row slides in from the left, then its three cells appear one by one.
export function revealRow(row: Element) {
	if (still()) return;
	gsap.fromTo(
		row,
		{ x: -12, opacity: 0 },
		{
			x: 0,
			opacity: 1,
			duration: 0.38,
			ease: "power2.out",
			clearProps: "transform,opacity",
		},
	);
	const cells = row.querySelectorAll("[data-cell]");
	if (!cells.length) return; // a message or a report: no scores
	gsap.fromTo(
		cells,
		{ opacity: 0 },
		{
			opacity: 1,
			duration: 0.24,
			stagger: 0.1,
			delay: 0.15,
			ease: "steps(3)",
			clearProps: "opacity",
		},
	);
}

// A list scrolls to its end, gliding.
export function scrollToEnd(el: HTMLElement) {
	if (still()) el.scrollTop = el.scrollHeight;
	else
		gsap.to(el, {
			scrollTop: el.scrollHeight,
			duration: 0.45,
			ease: "power2.out",
		});
}

// One element arrives from an offset, fading in: the hold banner from above, the hold pane
// from the right.
export function arrive(
	el: Element | null,
	from: gsap.TweenVars,
	duration: number,
) {
	if (!el || still()) return;
	gsap.from(el, {
		...from,
		opacity: 0,
		duration,
		ease: "power3.out",
		clearProps: "transform,opacity",
	});
}

// A replay result appears in four steps.
export function stepIn(els: Element[], gap: number) {
	if (still() || !els.length) return;
	gsap.fromTo(
		els,
		{ opacity: 0, x: -8 },
		{
			opacity: 1,
			x: 0,
			duration: 0.28,
			stagger: gap,
			ease: "steps(4)",
			clearProps: "transform,opacity",
		},
	);
}

// The facts popovers (<details data-pop>): rise in when opened, sink out when closed, and
// close on a click outside or on Esc.
const closing = new WeakSet<Element>();

export function closePop(d: HTMLDetailsElement) {
	const body = d.querySelector("[data-pop-body]");
	if (!body || still()) {
		d.open = false;
		return;
	}
	if (closing.has(d)) return;
	closing.add(d);
	gsap.to(body, {
		opacity: 0,
		y: 8,
		scale: 0.98,
		duration: 0.16,
		ease: "power1.in",
		onComplete: () => {
			d.open = false;
			closing.delete(d);
			gsap.set(body, { clearProps: "opacity,transform" });
		},
	});
}

export const closePops = () => {
	for (const d of document.querySelectorAll<HTMLDetailsElement>(
		"details[data-pop][open]",
	))
		closePop(d);
};

export function usePopovers() {
	useEffect(() => {
		const click = (e: MouseEvent) => {
			const t = e.target instanceof Element ? e.target : null;
			for (const d of document.querySelectorAll<HTMLDetailsElement>(
				"details[data-pop][open]",
			))
				if (!t || !d.contains(t)) closePop(d);
			const d = t?.closest("summary")?.parentElement;
			const body = d?.querySelector("[data-pop-body]");
			if (!(d instanceof HTMLDetailsElement) || !body || still()) return;
			if (d.open) {
				e.preventDefault();
				closePop(d);
			} else
				requestAnimationFrame(() =>
					gsap.fromTo(
						body,
						{ opacity: 0, y: 8, scale: 0.98 },
						{
							opacity: 1,
							y: 0,
							scale: 1,
							duration: 0.22,
							ease: "power2.out",
							clearProps: "opacity,transform",
						},
					),
				);
		};
		document.addEventListener("click", click, true);
		return () => document.removeEventListener("click", click, true);
	}, []);
}
