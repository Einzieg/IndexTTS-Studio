/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        body: ["Manrope", "ui-sans-serif", "system-ui"],
        display: ["Space Grotesk", "ui-sans-serif", "system-ui"]
      },
      boxShadow: {
        panel: "0 24px 48px -12px rgba(15, 23, 42, 0.12)"
      },
      colors: {
        shell: "#f2f2f7",
        graphite: "#1c1c1e",
        mist: "#e4e6eb",
        ink: "#101216",
        steel: "#5c6678",
        frost: "rgba(255, 255, 255, 0.6)"
      }
    }
  },
  plugins: []
};
