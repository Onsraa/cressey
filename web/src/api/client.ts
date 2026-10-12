export class ApiError extends Error {
	readonly status: number;
	readonly body: unknown;
	constructor(status: number, body: unknown) {
		super(`API ${status}`);
		this.status = status;
		this.body = body;
	}
}

// The control plane's key (CRESSEY_ADMIN_TOKEN), kept in this browser only; where storage
// is blocked it lasts until the page closes. Agents never hold it.
const ADMIN_KEY = "cressey.admin";
let adminInMemory = "";

export function adminToken(): string {
	try {
		return localStorage.getItem(ADMIN_KEY) ?? adminInMemory;
	} catch {
		return adminInMemory;
	}
}

export function setAdminToken(token: string) {
	adminInMemory = token;
	try {
		localStorage.setItem(ADMIN_KEY, token);
	} catch {
		// blocked storage: the key lasts until the page closes
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const headers = new Headers(init?.headers);
	const token = adminToken();
	if (token) headers.set("Authorization", `Bearer ${token}`);
	const r = await fetch(`/api${path}`, { ...init, headers });
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

export const apiPut = <T>(path: string, body: unknown) =>
	request<T>(path, {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
