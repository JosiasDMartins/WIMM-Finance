#!/bin/bash
# Build TailwindCSS for production - Multi-platform support

TAILWIND_VERSION="v3.4.17"
ARCH=$(uname -m)
OS=$(uname -s)

# Determine the correct binary to download
if [ "$OS" == "Linux" ]; then
    if [ "$ARCH" == "x86_64" ]; then
        BINARY="tailwindcss-linux-x64"
    elif [ "$ARCH" == "aarch64" ] || [ "$ARCH" == "arm64" ]; then
        BINARY="tailwindcss-linux-arm64"
    else
        echo "Unsupported architecture: $ARCH"
        exit 1
    fi
elif [ "$OS" == "Darwin" ]; then
    if [ "$ARCH" == "arm64" ]; then
        BINARY="tailwindcss-macos-arm64"
    else
        BINARY="tailwindcss-macos-x64"
    fi
else
    echo "Unsupported OS: $OS"
    exit 1
fi

# Download if not exists
if [ ! -f "$BINARY" ]; then
    echo "Downloading TailwindCSS v3 CLI for $OS $ARCH..."
    curl -sLO "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${BINARY}"
    chmod +x "$BINARY"
fi

# Build CSS
echo "Building TailwindCSS..."
./$BINARY -i finances/static/finances/css/tailwind-input.css -o finances/static/finances/css/tailwind.css --minify
echo "Done!"
