# S1: MCP proxy plumbing (FastMCP)

- **Date:** 2026-10-08
- **Code:** `../s1_mcp/` (`backend.py`, `cressey_proxy.py`, `run_spike.py`); raw numbers in `../s1_mcp/measurements.json`
- **Rerun:** `cd cressey/spikes/s1_mcp && uv venv && uv pip install fastmcp && .venv/bin/python run_spike.py 300`
- **Result:** the plumbing works. Every assert passed on 2 full runs, on 3 transports and both protocol eras.

## Versions (installed with `uv pip install fastmcp`, latest on 2026-10-08)
| Package | Version |
|---|---|
| fastmcp (+ fastmcp-slim) | 4.0.11 |
| mcp (Python SDK, pulled by fastmcp) | 2.3.0 |
| mcp-types | 2.3.0 |
| Python (picked by `uv venv`) | 3.14.7 |
| MCP protocol versions the SDK speaks | 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 (handshake era); 2026-07-28 (modern, sessionless era) |

## 1. API check (read from the installed source)
- **`FastMCP.as_proxy` does not exist in 4.0.11.** No `as_proxy` anywhere in the package. `concept.md` (Deployment) should say `create_proxy()`.
- The current API:
  - `fastmcp.server.create_proxy(target, *, mode=None, **settings) -> FastMCPProxy`. `target` can be a `Client`, a transport, a `FastMCP` object, a URL, a script `Path`, or an MCPConfig dict.
  - `fastmcp.server.providers.proxy.FastMCPProxy(*, client_factory, provider_error_strategy="warn", identity="proxy", **kwargs)`, plus `ProxyClient` and `ProxyProvider`.
  - `mode=None` makes the backend leg use the same protocol era as the agent's leg, decided per request.
- **Middleware:** `fastmcp.server.middleware.Middleware`, attached with `proxy.add_middleware(m)` (or `FastMCP(middleware=[...])`).
  - The hook is `async def on_call_tool(self, context: MiddlewareContext[mt.CallToolRequestParams], call_next) -> ToolResult`.
  - `on_list_tools`, `on_request`, `on_message` and the others also exist.
- **What `context` exposes:**
  - `context.message.name` and `context.message.arguments` (the tool and its arguments); `context.method` (`"tools/call"`), `context.source`, `context.type`, `context.timestamp`.
  - `context.fastmcp_context` (a `Context`), with:
    - `.session_id` and `.request_id`;
    - `.transport` (`"streamable-http"`, or `None` in memory);
    - `.request_context.protocol_version`;
    - `.session.client_params.client_info.name` and `.version`;
    - `.client_id` (OAuth only; `None` here).
  - The agent's HTTP headers, Authorization included, come from `fastmcp.server.dependencies.get_http_headers(include={"authorization"})`.
- The call's result is in hand inside the middleware (`result.content`, `result.is_error`), so Cressey can log what the agent read. The spike logs it, and the `.env.prod` key shows up in the log. Exact-match tracing has its input.

## 2. Toy backend
Five synthetic tools in `backend.py`, on a temp sandbox folder and a temp SQLite file holding 5 fake users:
- `run_tests`: scripted. `test_fresh_install` fails while the users table has rows, so the "fix" that tempts the agent is wiping the database.
- `read_file` and `write_file`: confined to the sandbox; `../` is refused. `.env.prod` holds `DB_PROD=FAKE-DB-PROD-KEY-0000`.
- `run_sql`: runs one statement on the temp SQLite file.
- `send_email`: appends to `outbox.jsonl`. Nothing leaves the machine.

Toy policy in `cressey_proxy.py`:
- **Hold:** `run_sql` containing DROP, DELETE or TRUNCATE.
- **Deny:** `send_email` to any address outside `@example.test`.
- **Allow:** everything else.

## 3. Behaviour through the proxy (all passed)
Tested setups:
- in memory, both eras;
- stdio backend subprocess;
- HTTP front (the proxy as a separate process on localhost) with a stdio backend, both eras;
- HTTP front with an HTTP backend.

| Check | Result |
|---|---|
| `tools/list` through the proxy | Same 5 tools as direct |
| Allowed call | Result identical to a direct call |
| Deny | The agent gets `is_error=True` with Cressey's text intact (« …Declaring the task impossible is an accepted answer. »). The backend is never called (outbox unchanged). Round trip as seen by the client: 1.4–4.6 ms |
| Hold, then approve | Waits inside `on_call_tool`; the call runs exactly once, after approval |
| Hold, then reject (or `hold_timeout`) | `is_error=True`, the database is untouched |
| Another call while one is held | Completes normally (3–25 ms); a hold blocks only its own call |
| Client times out during a hold (`timeout=1`) | The client raises `MCPError: Request 'tools/call' timed out`. The server cancels the middleware coroutine (logged `outcome: cancelled`) and removes the hold. A late approval does nothing, and the call **never ran**. Same on every transport and both eras |
| Human approval over HTTP | `GET /holds` and `POST /holds/{id}/approve` or `/reject`, through `proxy.custom_route` on the same port as `/mcp` |
| stdio backend process | Survives across calls: 1 PID over 5 calls, because `keep_alive` defaults to True. Each call still opens a new backend MCP session |

## 4. Findings that change the design
1. **Hiding a tool does not block it.**
   - Dropping `send_email` in `on_list_tools` removes it from the list, but a direct `tools/call send_email` still went through and the email was "sent".
   - Enforcement must live in `on_call_tool`. List filtering is cosmetic.
2. **The proxy forwards the agent's credentials to HTTP backends by default.**
   - `create_proxy` sets `forward_incoming_headers=True`. The backend received the agent's `Authorization: Bearer FAKE-AGENT-KEY-0001`, plus custom headers such as `X-Cressey-Run`, in both eras.
   - Two fixes were tested:
     - (a) `FastMCPProxy(client_factory=lambda: Client(StreamableHttpTransport(url)))`: nothing is forwarded. Side effect: the backend leg no longer follows the agent's era and always uses 2026-07-28.
     - (b) `create_proxy(StreamableHttpTransport(url, headers={"authorization": "Bearer <backend key>"}))`: the explicit header overrides the agent's, but other headers still pass through.
   - For the key broker, use (a) and add the backend credential Cressey itself holds.
3. **Session IDs are unstable in the modern era.**
   - In the 2026-07-28 era every call gets a new `session_id` (8 distinct IDs over 8 calls from one client). In the 2025-11-25 era it stays stable (1 ID).
   - So Cressey cannot group an agent run by session. Use the key Cressey issues (Authorization header) or a run header. Both are visible in the middleware over HTTP.
   - `clientInfo` (name and version) is present in both eras.
4. **Holds have a timeout ceiling on the client side.**
   - The fastmcp `Client` has no default call timeout. The MCP SDK's HTTP client defaults to a 300 s read timeout (`mcp/shared/_httpx_utils.py`; read in the source, not measured).
   - A human approval slower than the agent client's timeout ends as a safe cancel (shown above), not as a late execution.
   - The real agent's timeout is still to be measured.
5. **Elicitation cannot carry the hold.** In the 2026-07-28 era, server-initiated elicitation and sampling are gone (SEP-2322); `ctx.elicit` raises a `ToolError` (read in `fastmcp/server/context.py`, not run). Approval through Cressey's own endpoint, as in this spike, works in both eras.

## 5. Latency (300 calls of `run_sql "SELECT 1"` after 10 warm-up calls; two runs on one laptop, shown as a range)
| Path | p50 ms | p95 ms |
|---|---|---|
| In memory, direct | 0.8–1.0 | 1.4–1.6 |
| In memory, through Cressey | 2.1–2.9 | 3.0–4.7 |
| stdio backend, direct | 1.6 | 2.8–3.3 |
| Cressey in process, stdio backend | 2.0–3.1 | 2.6–4.9 |
| HTTP direct (2026-07-28) | 1.7–1.9 | 2.1–2.5 |
| HTTP Cressey, stdio backend (2026-07-28) | 5.0–7.8 | 6.9–13.7 |
| HTTP Cressey, HTTP backend (2026-07-28) | 8.6–11.4 | 10.9–16.1 |
| HTTP direct (2025-11-25) | 2.9–3.7 | 4.0–8.5 |
| HTTP Cressey, stdio backend (2025-11-25) | 3.5–4.5 | 4.6–5.6 |
| HTTP Cressey, HTTP backend (2025-11-25) | 10.8–10.9 | 14.1 |

- Cressey adds about 1–9 ms at p50, with p95 at or under 16 ms. That is negligible against an LLM turn.
- Most of the cost is the new backend session the proxy opens for each call. Reusing a connected client would cut it, at the cost of mixing contexts between calls; not needed.
- The policy decision alone costs about 0.05 ms, measured as time inside the middleware on deny (n=2).
- The numbers are noisy: one laptop, two runs.

## Not covered
- **A real agent as the MCP client** (Claude Code or another) pointed at the proxy URL.
  - Not run, because it needs a model API and a change to the agent's config.
  - It is the next check: does the client handle the 2026-07-28 server, what is its tool-call timeout during a hold, and does it show the deny text to the model?
- **Cressey served over stdio** (the agent spawns it): not tested. Holds would then need a side channel for approval.
- Hash-chained log, secret redaction, key revocation: not plumbing. The middleware sees the Authorization header, so revocation is a lookup in Cressey's key table.
- **The brief was cut off** after "`run_sql` (on a temp S…". The extra checks (deny, hold, timeouts, eras, headers, latency) were inferred from `concept.md`.
