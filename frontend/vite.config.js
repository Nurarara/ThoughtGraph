import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (id.includes("three")) {
                        return "three-vendor";
                    }
                    if (id.includes("react-force-graph-3d") || id.includes("3d-force-graph")) {
                        return "graph-3d";
                    }
                    if (id.includes("react-force-graph-2d") || id.includes("force-graph")) {
                        return "graph-2d";
                    }
                    if (id.includes("framer-motion")) {
                        return "motion";
                    }
                },
            },
        },
    },
});
