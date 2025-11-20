/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './finances/templates/**/*.html',
    './finances/static/finances/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        'primary': '#13a4ec',
        'primary-light': '#CCFBF1',
        'background-light': '#F8FAFC',
        'background-dark': '#0F172A'
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries'),
  ],
}
