import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
        devanagari: ["var(--font-devanagari)", "Noto Sans Devanagari", "sans-serif"],
      },
      colors: {
        saffron: { 50: "#fff8ed", 100: "#ffefd3", 500: "#f0932b", 600: "#e07a12", 700: "#ba5d0c", 900: "#7a3a0b" },
      },
    },
  },
  plugins: [],
};
export default config;
