import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const envRoot = "..";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envRoot, "");
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";
  const devHost = env.VITE_UI_DEV_HOST || "127.0.0.1";
  const devPort = Number(env.VITE_UI_DEV_PORT || "5173");

  return {
    base: "/ui/",
    envDir: envRoot,
    plugins: [react()],
    server: {
      host: devHost,
      port: devPort,
      proxy: {
        "/health": apiTarget,
        "/speakers": apiTarget,
        "/scripts": apiTarget,
        "/tts": apiTarget,
        "/jobs": apiTarget,
        "/audio": apiTarget,
        "/files": apiTarget
      }
    }
  };
});
