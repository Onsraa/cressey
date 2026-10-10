import { afterEach, expect, mock, test } from "bun:test";
import { ApiError, apiGet, apiPost } from "./client";

const realFetch = globalThis.fetch;
afterEach(() => {
	globalThis.fetch = realFetch;
});

const respond = (status: number, body: unknown) => {
	globalThis.fetch = mock(
		async () => new Response(JSON.stringify(body), { status }),
	) as unknown as typeof fetch;
};

test("apiGet resolves parsed JSON on 200", async () => {
	respond(200, { status: "ok" });
	expect(await apiGet<{ status: string }>("/health")).toEqual({ status: "ok" });
});

test("apiGet rejects with ApiError on 404", async () => {
	respond(404, { detail: "Not Found" });
	const err: unknown = await apiGet("/nope").catch((e: unknown) => e);
	expect(err).toBeInstanceOf(ApiError);
	expect(err instanceof ApiError && err.status).toBe(404);
});

test("apiPost sends JSON to /api", async () => {
	respond(201, { id: "g1" });
	await apiPost("/guides", { a: 1 });
	const [url, init] = (globalThis.fetch as unknown as ReturnType<typeof mock>)
		.mock.calls[0];
	expect(url).toBe("/api/guides");
	expect(init.method).toBe("POST");
	expect(init.body).toBe('{"a":1}');
});
