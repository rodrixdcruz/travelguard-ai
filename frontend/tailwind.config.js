/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'sans-serif'],
      },
      colors: {
        ink: {
          950: '#05080f',
          900: '#0a0f1a',
          800: '#0f1626',
          700: '#16203a',
        },
        accent: {
          DEFAULT: '#22d3ee',
          soft: '#67e8f9',
        },
        risk: {
          low: '#2dd4bf',
          moderate: '#fbbf24',
          high: '#fb923c',
          critical: '#f87171',
        },
      },
      boxShadow: {
        glow: '0 0 24px rgba(34, 211, 238, 0.15)',
      },
    },
  },
  plugins: [],
}
