// Numbers in English, as the interface is: “0.84”, “100%”.
export const num = (v: number, digits = 0) =>
	v.toLocaleString("en-US", {
		minimumFractionDigits: digits,
		maximumFractionDigits: digits,
	});

export const signed = (v: number, digits = 0) =>
	v.toLocaleString("en-US", {
		signDisplay: "exceptZero",
		minimumFractionDigits: digits,
		maximumFractionDigits: digits,
	});

export const pct = (v: number) =>
	v.toLocaleString("en-US", { style: "percent" });

// One decimal under 10 ms (“0.8”), none above (“856”). Null: nothing was measured.
export const ms = (v: number | null) =>
	v === null ? "—" : num(v, v < 10 ? 1 : 0);

export const seconds = (v: number) => num(v / 1000, 1);

export const day = (iso: string) => iso.slice(0, 10); // 2026-10-10

// The share of sessions held; a report with no session of a kind shows 0.
export const share = (held: number, total: number) =>
	total ? held / total : 0;

// “n = 31” stays on one line.
export const sample = (k: number | string) => `n = ${k}`;
