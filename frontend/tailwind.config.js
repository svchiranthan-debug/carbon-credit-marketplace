/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Professional Natural Agricultural Greens
        forest: {
          50: '#f2f7f4',
          100: '#e1ede5',
          200: '#c5dcce',
          300: '#9ec3ac',
          400: '#71a384',
          500: '#4e8563',
          600: '#396b4c',
          700: '#2d543c',
          800: '#264432',
          900: '#1b3325', // Primary agricultural brand green
          950: '#0e1d15',
        },
        // Warm Earth / Soil / Sand Accents
        earth: {
          50: '#f9f8f6',
          100: '#f3efe9',
          200: '#e6ded3',
          300: '#d4c5b2',
          400: '#bda68c',
          500: '#9e8469',
          600: '#7d644d',
          700: '#644e3d',
          800: '#524134',
          900: '#44372d',
        },
        // Clean neutral slate
        charcoal: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      borderRadius: {
        'lg': '0.5rem',
        'xl': '0.75rem',
        '2xl': '1rem',
      }
    },
  },
  plugins: [],
}
