import { expect, test } from "bun:test";
import { cn } from "./utils";

test("cn merges tailwind classes", () => {
	expect(cn("p-2", "p-4")).toBe("p-4");
});
