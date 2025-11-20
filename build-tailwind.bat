@echo off
REM Build TailwindCSS for production
echo Building TailwindCSS...
tailwindcss-v3-windows-x64.exe -i finances/static/finances/css/tailwind-input.css -o finances/static/finances/css/tailwind.css --minify
echo Done!
