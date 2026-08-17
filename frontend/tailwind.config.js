/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // IEEE brand palette. `ieee.600` is the primary action colour and meets
        // AA contrast on white; `navy` carries structure and headings.
        ieee: {
          50: '#EEF7FC',
          100: '#D6EDF8',
          200: '#AEDAF1',
          300: '#77C2E7',
          400: '#3AA4D8',
          500: '#0F86C4',
          600: '#00629B', // IEEE blue
          700: '#014E7C',
          800: '#053F63',
          900: '#0B2545',
          950: '#061729',
        },
        navy: {
          50: '#F4F6F9',
          100: '#E6EBF2',
          200: '#CCD6E4',
          300: '#A3B4CC',
          400: '#7389AB',
          500: '#526A8E',
          600: '#3F5474',
          700: '#34445E',
          800: '#2E3B50',
          900: '#0B2545',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          subtle: '#F8FAFC',
          muted: '#F1F5F9',
          inverted: '#0B2545',
        },
        success: {
          50: '#ECFDF5',
          100: '#D1FAE5',
          500: '#10B981',
          600: '#059669',
          700: '#047857',
        },
        warning: {
          50: '#FFFBEB',
          100: '#FEF3C7',
          500: '#F59E0B',
          600: '#D97706',
          700: '#B45309',
        },
        danger: {
          50: '#FEF2F2',
          100: '#FEE2E2',
          500: '#EF4444',
          600: '#DC2626',
          700: '#B91C1C',
        },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        display: ['Space Grotesk', 'Inter var', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['Source Serif 4', 'Georgia', 'ui-serif', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.02em' }],
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        // Deliberately soft and low-contrast — depth without visual noise.
        card: '0 1px 2px rgba(11, 37, 69, 0.04), 0 1px 3px rgba(11, 37, 69, 0.06)',
        'card-hover': '0 4px 12px rgba(11, 37, 69, 0.08), 0 2px 4px rgba(11, 37, 69, 0.04)',
        panel: '0 12px 32px rgba(11, 37, 69, 0.12), 0 2px 8px rgba(11, 37, 69, 0.06)',
        focus: '0 0 0 3px rgba(0, 98, 155, 0.25)',
      },
      spacing: {
        18: '4.5rem',
        68: '17rem',
      },
      maxWidth: {
        phone: '26rem',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'slide-up': 'slide-up 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-right': 'slide-in-right 220ms cubic-bezier(0.16, 1, 0.3, 1)',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
};
