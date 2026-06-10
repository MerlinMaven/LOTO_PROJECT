/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Industrial control-room palette
        steel: {
          50: "#f5f7fa",
          100: "#e9eef4",
          200: "#cdd9e5",
          300: "#a3b6cc",
          400: "#7390ad",
          500: "#516f8f",
          600: "#3f5874",
          700: "#34485e",
          800: "#2d3d4f",
          900: "#1c2733",
          950: "#11181f",
        },
        // Status semantics
        draft: "#b45309",      // amber-700  — needs review
        approved: "#15803d",   // green-700  — signed off
        published: "#1d4ed8",  // blue-700   — live
        archived: "#57534e",   // stone-600  — retired
        hazard: "#b91c1c",     // red-700
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
