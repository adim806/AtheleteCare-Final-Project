import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const webhookUrl =
    env.N8N_WEBHOOK_URL || "http://127.0.0.1:5678/webhook/athletecare-triage";
  let webhookOrigin = "http://127.0.0.1:5678";
  let webhookPath = "/webhook/athletecare-triage";
  try {
    const u = new URL(webhookUrl);
    webhookOrigin = u.origin;
    webhookPath = `${u.pathname}${u.search}`;
  } catch {
    /* keep defaults */
  }

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 8004,
      proxy: {
        "/api/ollama": {
          target: env.OLLAMA_URL || "http://127.0.0.1:11434",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/ollama/, ""),
        },
        "/api/triage": {
          target: webhookOrigin,
          changeOrigin: true,
          rewrite: () => webhookPath,
          timeout: 600_000,
          proxyTimeout: 600_000,
        },
      },
    },
    preview: {
      host: "0.0.0.0",
      port: 8004,
    },
  };
});
