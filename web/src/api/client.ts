export class ApiError extends Error {
	readonly status: number;
	readonly body: unknown;
	constructor(status: number, body: unknown) {
		super(`API ${status}`);
		this.status = status;
		this.body = body;
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const r = await fetch(`/api${path}`, init);
	const body = r.status === 204 ? null : await r.json().catch(() => null);
	if (!r.ok) throw new ApiError(r.status, body);
	return body as T;
}

export const apiGet = <T>(path: string) => request<T>(path);

export const apiPost = <T>(path: string, body: unknown) =>
	request<T>(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
