#!/usr/bin/env bash
# scripts/build-extension.sh
# Package the handover Chrome/Firefox extension into a zip ready for the Web Store.
# Usage: bash scripts/build-extension.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTENSION_DIR="$REPO_ROOT/extension"
DIST_DIR="$REPO_ROOT/dist/extension"
ZIP_NAME="handover-extension.zip"

echo "Building handover extension..."

# Generate placeholder icons if not present
# Real icons should be 16x16, 48x48, 128x128 PNG files.
# Replace the generated placeholders with proper branding before publishing.
ICONS_DIR="$EXTENSION_DIR/icons"
python3 - <<'PYEOF'
import struct, zlib, base64, pathlib, os

def make_png(size: int, r: int, g: int, b: int) -> bytes:
    """Create a minimal solid-colour PNG of the given size."""
    row = b"\x00" + bytes([r, g, b, 255]) * size
    raw = row * size
    compressed = zlib.compress(raw)
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

icons_dir = pathlib.Path(os.environ.get("ICONS_DIR", "extension/icons"))
icons_dir.mkdir(parents=True, exist_ok=True)

# Accent colour: #e94560 (R=233 G=69 B=96)
for size in (16, 48, 128):
    dest = icons_dir / f"icon-{size}.png"
    if not dest.exists():
        dest.write_bytes(make_png(size, 233, 69, 96))
        print(f"  Generated placeholder {dest.name}")
    else:
        print(f"  Icon {dest.name} already exists — skipping")
PYEOF

# Clean and recreate dist/extension
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Copy extension files (exclude source maps and dev-only files)
cp -r "$EXTENSION_DIR"/* "$DIST_DIR/"

# Remove icons placeholder note if it exists
rm -f "$DIST_DIR/icons/.gitkeep"

# Create zip
cd "$DIST_DIR"
zip -r "../$ZIP_NAME" . -x "*.DS_Store" -x "__MACOSX/*" >/dev/null

echo ""
echo "Built: dist/$ZIP_NAME"
echo ""
echo "Next steps:"
echo "  Chrome: chrome://extensions → Load unpacked → select extension/"
echo "  Chrome Web Store: upload dist/$ZIP_NAME"
echo "  Firefox: about:debugging → Load Temporary Add-on → select extension/manifest.json"
