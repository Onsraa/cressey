export { cn } from "cn";

export const isRecord = (v: unknown): v is Record<string, unknown> =>
	typeof v === "object" && v !== null && !Array.isArray(v);

// The ink, as index.css defines it (--color-ink), for a canvas: it can't read a CSS variable.
export const inkColor = () =>
	getComputedStyle(document.documentElement).getPropertyValue("--color-ink");
