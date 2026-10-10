import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
	// /mcp too: « Brancher un agent » shows this page's own origin as the MCP URL.
	server: {
		proxy: {
			"/api": "http://localhost:8000",
			"/mcp": "http://localhost:8000",
		},
	},
});
