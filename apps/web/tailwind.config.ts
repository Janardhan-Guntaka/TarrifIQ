import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#1d4ed8", dark: "#1e40af", light: "#3b82f6" },
      },
    },
  },
  plugins: [],
};

export default config;
