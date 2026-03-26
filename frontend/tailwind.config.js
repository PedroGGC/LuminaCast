/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        lunima: {
          black: "#141414",
          dark: "#181818",
          card: "#2f2f2f",
          gold: "#FFD700",
          "gold-hover": "#FFC107",
          gray: "#808080",
          "light-gray": "#b3b3b3",
        },
      },
      fontFamily: {
        sans: ["Inter", "Helvetica Neue", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
