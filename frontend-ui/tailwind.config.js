/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#182230",
        muted: "#667085",
        line: "#e7ebf0",
        brand: "#5263d8",
        "brand-soft": "#eef0ff",
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px rgba(16, 24, 40, 0.03)",
      },
    },
  },
  plugins: [],
};
