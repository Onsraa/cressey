import { expect, test } from "bun:test";
import { ApiError } from "@/api/client";
import { failure } from "./decide";

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
