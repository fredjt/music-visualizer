"""
Shared color utilities for visualizer plugins.

Provides a unified API for parsing and formatting colors across all plugins.
Supports named colors (red, blue, etc.) and hex colors (#RRGGBB).

All visualizer plugins should use ColorParser for color handling instead of
hardcoding color values. This ensures consistent behavior and simplifies
adding new color-related features.

Usage:
    parser = ColorParser("red, #00ff00, blue")
    # or
    parser = ColorParser(["red", "#00ff00", "blue"])

    parser.as_hex_list()        → ["ff0000", "00ff00", "0000ff"]
    parser.as_colormapping()    → "ff0000,00ff00,0000ff"
    parser.as_pipe_colors()     → "red|green|blue"
    parser.as_rgb_tuple(0)      → (255, 0, 0)
    parser.as_bg_color()        → "000000" (black)
    parser.as_spectrum_mode()   → ("colormapping", "ff0000,00ff00,0000ff")
    parser.as_cqt_scheme()      → "1.0|0.5|0|0.0|0.5|1.0"
"""

from __future__ import annotations

import re

# Named CSS/HTML colors → hex mapping (common subset)
NAMED_COLORS: dict[str, str] = {
    "black": "000000",
    "white": "ffffff",
    "red": "ff0000",
    "green": "00ff00",
    "blue": "0000ff",
    "yellow": "ffff00",
    "cyan": "00ffff",
    "magenta": "ff00ff",
    "orange": "ffa500",
    "purple": "800080",
    "pink": "ffc0cb",
    "brown": "a52a2a",
    "gray": "808080",
    "grey": "808080",
    "maroon": "800000",
    "navy": "000080",
    "olive": "808000",
    "lime": "00ff00",
    "aqua": "00ffff",
    "teal": "008080",
    "silver": "c0c0c0",
    "fuchsia": "ff00ff",
    "coral": "ff7f50",
    "gold": "ffd700",
    "crimson": "dc143c",
    "indigo": "4b0082",
    "violet": "ee82ee",
    "turquoise": "40e0d0",
    "salmon": "fa8072",
    "tomato": "ff6347",
    "wheat": "f5deb3",
    "ivory": "fffff0",
    "khaki": "f0e68c",
    "lavender": "e6e6fa",
    "peru": "cd853f",
    "plum": "dda0dd",
    "orchid": "da70d6",
    "sienna": "a0522d",
    "tan": "d2b48c",
    "thistle": "d8bfd8",
    "snow": "fffafa",
    "linen": "faf0e6",
    "beige": "f5f5dc",
    "mistyrose": "ffe4e1",
    "antiquewhite": "faebd7",
    "floralwhite": "fffaf0",
    "aliceblue": "f0f8ff",
    "ghostwhite": "f8f8ff",
    "honeydew": "f0fff0",
    "azure": "f0ffff",
    "seashell": "fff5ee",
    "oldlace": "fdf5e6",
    "lightyellow": "ffffe0",
    "lemonchiffon": "fffacd",
    "lightcyan": "e0ffff",
    "lightpink": "ffb6c1",
    "lightsalmon": "ffa07a",
    "lightseagreen": "20b2aa",
    "lightskyblue": "87cefa",
    "lightslategray": "778899",
    "lightsteelblue": "b0c4de",
    "lightgoldenrodyellow": "fafad2",
    "lightgrey": "d3d3d3",
    "lightgray": "d3d3d3",
    "darkred": "8b0000",
    "darkgreen": "006400",
    "darkblue": "00008b",
    "darkcyan": "008b8b",
    "darkmagenta": "8b008b",
    "darkyellow": "bdb76b",
    "darkorange": "ff8c00",
    "darkviolet": "9400d3",
    "darkslategray": "2f4f4f",
    "darkslategrey": "2f4f4f",
    "darkturquoise": "00ced1",
    "darkgoldenrod": "b8860b",
    "darkkhaki": "bdb76b",
    "darkorchid": "9932cc",
    "darksalmon": "e9967a",
    "darkseagreen": "8fbc8f",
    "darkslateblue": "483d8b",
    "darkolivegreen": "556b2f",
}


class ColorParser:
    """
    Parse and format colors for ffmpeg visualizer filters.

    Supports:
    - Named colors: "red", "blue", "crimson", etc.
    - Hex colors: "#ff0000", "ff0000"

    Usage:
        parser = ColorParser("red, #00ff00, blue")
        # or
        parser = ColorParser(["red", "#00ff00", "blue"])

        parser.as_hex_list()        → ["ff0000", "00ff00", "0000ff"]
        parser.as_colormapping()    → "ff0000,00ff00,0000ff"
        parser.as_pipe_colors()     → "red|green|blue"
        parser.as_rgb_tuple(0)      → (255, 0, 0)
    """

    def __init__(self, colors: str | list[str] | None = None):
        """
        Initialize with a color string or list of color strings.

        Args:
            colors: A comma-separated string or a list of color strings.
                    Each color can be a named color ("red") or hex ("#ff0000").
        """
        if colors is None:
            self._raw_colors: list[str] = []
            return

        if isinstance(colors, str):
            self._raw_colors = [c.strip() for c in colors.split(",") if c.strip()]
        else:
            self._raw_colors = [str(c).strip() for c in colors if str(c).strip()]

    def _resolve_color(self, color: str) -> str:
        """
        Resolve a single color string to a 6-digit hex string.

        Args:
            color: A color string (named or hex)

        Returns:
            6-digit hex string (no # prefix)

        Raises:
            ValueError: If the color is not recognized
        """
        color = color.strip().lower()

        # Check named colors
        if color in NAMED_COLORS:
            return NAMED_COLORS[color]

        # Check hex format
        hex_match = re.match(r"^#?([0-9a-f]{6})$", color)
        if hex_match:
            return hex_match.group(1)

        raise ValueError(f"Unknown color: {color!r}")

    @property
    def resolved(self) -> list[str]:
        """List of resolved 6-digit hex strings."""
        return [self._resolve_color(c) for c in self._raw_colors]

    @property
    def count(self) -> int:
        """Number of colors."""
        return len(self._raw_colors)

    @property
    def is_empty(self) -> bool:
        """True if no colors provided."""
        return len(self._raw_colors) == 0

    def as_hex_list(self) -> list[str]:
        """Return resolved colors as a list of 6-digit hex strings."""
        return self.resolved

    def as_colormapping(self) -> str:
        """
        Return colors formatted for ffmpeg's colormapping parameter.

        Example: "ff0000,00ff00,0000ff"
        """
        return ",".join(self.resolved)

    def as_pipe_colors(self) -> str:
        """
        Return colors formatted for ffmpeg's colors parameter (pipe-separated).

        Uses named color names where possible, falls back to hex.
        When multiple names map to the same hex (e.g., green/lime),
        prefers the first one found in NAMED_COLORS.

        Example: "red|green|blue"
        """
        # Build reverse map preferring first occurrence (shorter/more common names)
        reverse_map: dict[str, str] = {}
        for name, hex_val in NAMED_COLORS.items():
            if hex_val not in reverse_map:
                reverse_map[hex_val] = name
        parts = []
        for hex_color in self.resolved:
            name = reverse_map.get(hex_color, hex_color)
            parts.append(name)
        return "|".join(parts)

    def as_rgb_tuple(self, index: int = 0) -> tuple[int, int, int]:
        """
        Return RGB values (0-255) for a given color index.

        Args:
            index: Index of the color to retrieve (default: 0)

        Returns:
            (r, g, b) tuple

        Raises:
            IndexError: If index is out of range
        """
        hex_color = self.resolved[index]
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)

    def as_rgb_floats(self, index: int = 0) -> tuple[float, float, float]:
        """
        Return RGB values (0.0-1.0) for a given color index.

        Args:
            index: Index of the color to retrieve (default: 0)

        Returns:
            (r, g, b) tuple with float values
        """
        r, g, b = self.as_rgb_tuple(index)
        return (r / 255.0, g / 255.0, b / 255.0)

    def as_bg_color(self) -> str:
        """
        Return the first color as a hex string for use as a background color.

        If no colors are provided, returns '000000' (black).

        Returns:
            6-digit hex string for background color
        """
        if self._raw_colors:
            return self.resolved[0]
        return "000000"  # black

    def as_spectrum_mode(self) -> tuple[str, str]:
        """
        Return the appropriate color mode and colormapping string for spectrum filters.

        If 2+ colors are provided, returns ('colormapping', 'hex1,hex2,...').
        Otherwise returns ('intensity', '').

        Returns:
            Tuple of (mode, colormapping_string)
        """
        if self.count >= 2:
            return ("colormapping", self.as_colormapping())
        return ("intensity", "")

    def as_cqt_scheme(self) -> str:
        """
        Return a color scheme string for ffmpeg's showcqt cscheme parameter.

        If 2+ colors are provided, converts them to R.G.B.R.G.B format.
        Otherwise returns the default scheme: '1.0|0.5|0|0.0|0.5|1.0' (red-orange-blue gradient).

        Returns:
            cscheme string for showcqt
        """
        if self.count >= 2:
            parts = []
            for hex_c in self.resolved[:6]:  # Use up to 6 colors
                r = int(hex_c[0:2], 16) / 255.0
                g = int(hex_c[2:4], 16) / 255.0
                b = int(hex_c[4:6], 16) / 255.0
                parts.extend([str(r), str(g), str(b)])
            return "|".join(parts)
        # Default: red-orange-blue gradient
        return "1.0|0.5|0|0.0|0.5|1.0"

    def as_waves_colors(self) -> str:
        """
        Return pipe-separated colors for ffmpeg's showwaves colors parameter.

        If no colors are provided, returns 'red|green|blue' (default).

        Returns:
            Pipe-separated color string
        """
        if self._raw_colors:
            return self.as_pipe_colors()
        return "red|green|blue"

    def as_glow_params(
        self,
        index: int = 0,
        alpha_multiplier: float = 0.08,
        mix_multiplier: float = 0.15,
    ) -> tuple[float, float, float, float]:
        """
        Return parameters for a color glow overlay.

        Falls back to default magenta glow (0.1, 0.05, 0.2, 0.08) if no colors
        are provided or the index is out of range.

        Args:
            index: Index of the color to use (default: 0)
            alpha_multiplier: Alpha multiplier for the glow overlay
            mix_multiplier: Color channel mix multiplier

        Returns:
            (glow_rr, glow_gg, glow_bb, glow_alpha) for colorchannelmixer
        """
        try:
            r, g, b = self.as_rgb_floats(index)
            return (
                r * mix_multiplier,
                g * mix_multiplier,
                b * mix_multiplier,
                alpha_multiplier,
            )
        except (ValueError, IndexError):
            # Default magenta glow
            return (0.1, 0.05, 0.2, alpha_multiplier)

    def as_vectorscope_params(
        self,
        index: int = 0,
        default_r: int = 255,
        default_g: int = 255,
        default_b: int = 255,
    ) -> tuple[int, int, int]:
        """
        Return RGB values for vectorscope color contrast parameters.

        Falls back to white (255,255,255) if color can't be parsed or index is out of range.

        Args:
            index: Index of the color to use (default: 0)
            default_r: Default red contrast value if parsing fails (0-255)
            default_g: Default green contrast value if parsing fails (0-255)
            default_b: Default blue contrast value if parsing fails (0-255)

        Returns:
            (rc, gc, bc) tuple for vectorscope contrast parameters
        """
        try:
            return self.as_rgb_tuple(index)
        except (ValueError, IndexError):
            return (default_r, default_g, default_b)

    def __repr__(self) -> str:
        return f"ColorParser({self._raw_colors!r})"


# Convenience function for quick color parsing
def parse_colors(colors: str | list[str] | None = None) -> ColorParser:
    """
    Create a ColorParser from a color string or list.

    This is a convenience wrapper around ColorParser().

    Args:
        colors: A comma-separated string or a list of color strings.

    Returns:
        A ColorParser instance
    """
    return ColorParser(colors)
