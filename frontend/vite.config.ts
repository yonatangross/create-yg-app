import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
	plugins: [react()],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
	server: {
		port: 5173,
		host: true,
		proxy: {
			"/api": {
				target: process.env.VITE_API_URL || "http://localhost:8600",
				changeOrigin: true,
			},
		},
	},
	build: {
		rollupOptions: {
			output: {
				manualChunks: {
					vendor: ["react", "react-dom"],
					router: ["@tanstack/react-router"],
					query: ["@tanstack/react-query"],
				},
			},
		},
	},
});
