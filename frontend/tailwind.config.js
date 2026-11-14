/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        "surface-2": token("surface-2"),
        line: token("line"),
        text: token("text"),
        muted: token("muted"),
        accent: token("accent"),
        warm: token("warm"),
        prevention: token("prevention"),
        detection: token("detection"),
        suppression: token("suppression"),
        danger: token("danger"),
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { card: "12px" },
      maxWidth: { content: "1440px" },
    },
  },
  plugins: [],
};
