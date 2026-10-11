import { expect, test } from "bun:test";
import { ApiError } from "@/api/client";
import { failure, opened } from "./decide";

test("a reason that breaks a rule comes back with the rule named", () => {
	const broken = new ApiError(422, { detail: "names a trap key" });
	expect(failure(broken)).toBe("Reason not sent: names a trap key");
});

test("a hold nobody waits on, and any other failure, read plainly", () => {
	expect(failure(new ApiError(404, { detail: "no pending hold" }))).toBe(
		"This hold is no longer waiting for a decision.",
	);
	// FastAPI's own validation errors are a list: nothing to quote.
	expect(failure(new ApiError(422, { detail: [{ msg: "too long" }] }))).toBe(
		"Decision not saved: try again.",
	);
	expect(failure(new TypeError("Failed to fetch"))).toBe(
		"Decision not saved: try again.",
	);
});

test("opening the reason box seeds it from the draft once", () => {
	expect(opened(undefined, 4, "Draft.")).toEqual({
		n: 4,
		text: "Draft.",
		fresh: true,
	});
	// No draft yet: an empty box, which the human fills.
	expect(opened(undefined, 4, null).text).toBe("");
	// Opened again for the same hold (a shortcut): what was typed stays, the box wants focus.
	const typed = { n: 4, text: "Typed.", fresh: false };
	expect(opened(typed, 4, "A later draft.")).toEqual({ ...typed, fresh: true });
	// Another hold: its own draft.
	expect(opened(typed, 5, "Other.")).toEqual({
		n: 5,
		text: "Other.",
		fresh: true,
	});
});
