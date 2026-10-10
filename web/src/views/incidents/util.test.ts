import { expect, test } from "bun:test";
import { argPath, shortArgs } from "./util";

const names = new Map([["0123456789ab", "DB_PROD_KEY"]]);

test("argPath reads the path argument, and nothing else", () => {
	expect(argPath('{"path": ".env.prod"}')).toBe(".env.prod");
	expect(argPath('{"query": "DELETE FROM users"}')).toBeUndefined();
	expect(argPath('{"path": 3}')).toBeUndefined();
	expect(argPath('["path"]')).toBeUndefined();
	expect(argPath("not json")).toBeUndefined();
});

test("shortArgs keeps the values on one line, secrets by name", () => {
	const sql = '{"query": "DELETE FROM users", "key": "[secret:0123456789ab]"}';
	expect(shortArgs(sql, names)).toBe("DELETE FROM users ‹DB_PROD_KEY›");
	expect(shortArgs('{"key": "[secret:ffffffffffff]"}', names)).toBe("‹secret›");
	expect(shortArgs("{}", names)).toBe("");
	expect(shortArgs('{"content": "a\\n\\n  b", "n": 2}', names)).toBe("a b 2");
	expect(shortArgs(JSON.stringify({ q: "x".repeat(50) }), names, 10)).toBe(
		`${"x".repeat(9)}…`,
	);
	expect(shortArgs("not json", names)).toBe("not json");
});
