import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        fundo: "#080910",
        superficie: "#13151c",
        superficie2: "#1a1d27",
        borda: "#1a1d2e",
        texto: {
          primario: "#e4e4e7",
          secundario: "#a1a1aa",
          muted: "#71717a",
        },
        risco: {
          alto: "#ff2d4a",
          medio: "#f59e0b",
          baixo: "#22c55e",
        },
        accent: "#ff2d4a",
        accent2: "#6366f1",
      },
      fontFamily: {
        titulo: ["Syne", "sans-serif"],
        mono: ["Space Mono", "monospace"],
        body: ["DM Sans", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
