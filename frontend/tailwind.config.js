/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Sora", "ui-sans-serif", "system-ui"],
      },
      boxShadow: {
        universe: "0 24px 90px rgba(0, 0, 0, 0.34)",
      },
      keyframes: {
        "cloud-drift": {
          "0%": { transform: "translate3d(-4%, 0, 0)" },
          "100%": { transform: "translate3d(4%, 0, 0)" },
        },
        "tree-breathe": {
          "0%, 100%": { transform: "translate3d(0, 0, 0) scale(1)" },
          "50%": { transform: "translate3d(0.6%, -0.4%, 0) scale(1.008)" },
        },
        shimmer: {
          "0%, 100%": { opacity: "0.28", transform: "scale(0.92)" },
          "50%": { opacity: "1", transform: "scale(1.18)" },
        },
        "slow-glow": {
          "0%, 100%": { opacity: "0.65" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        "cloud-drift": "cloud-drift 22s ease-in-out infinite alternate",
        "tree-breathe": "tree-breathe 12s ease-in-out infinite",
        shimmer: "shimmer 4s ease-in-out infinite",
        "slow-glow": "slow-glow 7s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
