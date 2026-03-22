/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
    './lib/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        // SmartFactory 브랜드 컬러
        sf: {
          blue: '#2563EB',
          dark: '#0F172A',
          light: '#F8FAFC',
          accent: '#10B981',
          warn: '#F59E0B',
          danger: '#EF4444',
          cream: '#F1F5F9',
          beige: '#E2E8F0',
          pink: '#F472B6',
          brown: '#5C4A3D',
          yellow: '#FFD93D',
          orange: '#FF8C42',
        },
      },
      fontFamily: {
        sans: ['Pretendard', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Noto Sans KR', 'sans-serif'],
      },
      boxShadow: {
        'sf': '0 4px 12px 0 rgba(37, 99, 235, 0.18)',
        'sf-lg': '0 8px 24px -3px rgba(37, 99, 235, 0.22)',
        'sf-sm': '0 4px 12px rgba(37, 99, 235, 0.15)',
        'soft': '0 2px 8px rgba(15, 23, 42, 0.05)',
        'soft-lg': '0 8px 24px rgba(15, 23, 42, 0.08)',
        'lift': '0 12px 32px -8px rgba(37, 99, 235, 0.22), 0 4px 8px -2px rgba(0, 0, 0, 0.06)',
        'lift-lg': '0 20px 40px -12px rgba(37, 99, 235, 0.28), 0 8px 16px -4px rgba(0, 0, 0, 0.08)',
        'glow': '0 0 20px rgba(37, 99, 235, 0.15)',
        'inner-glow': 'inset 0 1px 2px rgba(255, 255, 255, 0.6)',
      },
      keyframes: {
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          '0%': { opacity: '0', transform: 'translateY(-12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'slide-up': 'slide-up 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slide-down 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in': 'fade-in 0.3s ease-out',
        'shimmer': 'shimmer 2s infinite linear',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
