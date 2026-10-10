// Numbers in French, as the interface is: « 0,84 », « 100 % ».
export const num = (v: number, digits = 0) =>
	v.toLocaleString("fr-FR", {
		minimumFractionDigits: digits,
		maximumFractionDigits: digits,
	});

export const signed = (v: number, digits = 0) =>
	v.toLocaleString("fr-FR", {
		signDisplay: "exceptZero",
		minimumFractionDigits: digits,
		maximumFractionDigits: digits,
	});

export const pct = (v: number) =>
	v.toLocaleString("fr-FR", { style: "percent" });

// One decimal under 10 ms (« 0,8 »), none above (« 856 »). Null: nothing was measured.
export const ms = (v: number | null) =>
	v === null ? "—" : num(v, v < 10 ? 1 : 0);

export const seconds = (v: number) => num(v / 1000, 1);

export const day = (iso: string) => new Date(iso).toLocaleDateString("fr-FR");

// The share of sessions held; a report with no session of a kind shows 0.
export const share = (held: number, total: number) =>
	total ? held / total : 0;

// « n = 31 » stays on one line, as French typography wants.
export const sample = (k: number | string) => `n\u00a0=\u00a0${k}`;
