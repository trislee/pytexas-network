import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import checker from "vite-plugin-checker";
import viteTsconfigPaths from "vite-tsconfig-paths";

/** GitHub project Pages use `/repo-name/`; user site repo uses `/`. Override: `VITE_BASE_PATH=... npm run build`. */
function appBase(): string {
  const explicit = process.env.VITE_BASE_PATH?.trim();
  if (explicit) {
    return explicit.endsWith("/") ? explicit : `${explicit}/`;
  }
  const gh = process.env.GITHUB_REPOSITORY;
  if (gh) {
    const repo = gh.split("/")[1] ?? "";
    if (repo.endsWith(".github.io")) {
      return "/";
    }
    return `/${repo}/`;
  }
  return "/";
}

export default defineConfig({
  base: appBase(),
  plugins: [
    react(),
    viteTsconfigPaths(),
    checker({
      typescript: {
        buildMode: true,
      },
    }),
  ],
  server: {
    open: false,
    port: 3000,
  },
  build: {
    outDir: "build",
  },
  resolve: {
    preserveSymlinks: false,
  },
});
