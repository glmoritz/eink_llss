"""
Frame Converter - Handles resampling of frames for different display bit depths.

This module converts PNG frames from HLSS to raw framebuffer formats
suitable for e-Ink displays with varying bit depths (1-bit, 2-bit, 4-bit, etc.).

For e-Ink displays:
- bit_depth=1: 1-bit monochrome (black/white), packed 8 pixels per byte
- bit_depth=2: 2-bit grayscale (4 gray levels), two separate 1-bit planes
  (EPD register 0x24 for MSB plane, 0x26 for LSB plane)
- bit_depth=4: 4-bit grayscale (16 gray levels)
- bit_depth=8: 8-bit grayscale (256 levels)
"""

import io
import logging
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def png_to_grayscale(png_data: bytes) -> Tuple[Image.Image, int, int]:
    """
    Load PNG data and convert to grayscale.

    Args:
        png_data: Raw PNG image data.

    Returns:
        Tuple of (grayscale_image, width, height).
    """
    image = Image.open(io.BytesIO(png_data))
    # Convert to grayscale (L mode = 8-bit grayscale)
    if image.mode != "L":
        image = image.convert("L")
    return image, image.width, image.height


def quantize_to_levels(value: int, source_bits: int, target_bits: int) -> int:
    """
    Quantize a pixel value from source bit depth to target bit depth.

    Args:
        value: Pixel value (0-255 for 8-bit, etc.).
        source_bits: Source bit depth (typically 8 for grayscale images).
        target_bits: Target bit depth (1, 2, 4, etc.).

    Returns:
        Quantized pixel value.
    """
    max_source = (1 << source_bits) - 1
    max_target = (1 << target_bits) - 1

    # Scale and round
    return round(value * max_target / max_source)


def _get_pixel_data(image: Image.Image) -> List[int]:
    """
    Extract pixel data from an image as a list of integers.

    Args:
        image: PIL grayscale image.

    Returns:
        List of pixel values (0-255 for grayscale).
    """
    return list(image.getdata())  # type: ignore[arg-type]


def convert_to_1bit_packed(image: Image.Image) -> bytes:
    """
    Convert grayscale image to 1-bit packed format.

    Each byte contains 8 packed pixels (MSB = leftmost pixel), bit 1 = white.

    The image is Floyd-Steinberg dithered down to pure black/white rather than
    hard-thresholded: on a 1bpp mono e-Ink panel the apparent shade comes from
    the dot pattern, so dithering preserves gradients that a 128 threshold would
    flatten. The device must NOT re-dither this output (driver dither=false).

    Args:
        image: PIL grayscale image.

    Returns:
        Packed 1-bit framebuffer data.
    """
    width, height = image.size

    # PIL "1" mode applies Floyd-Steinberg dithering by default, yielding 0/255.
    bw = image.convert("1")
    pixels = list(bw.getdata())

    # Calculate packed size (8 pixels per byte)
    packed_size = (width * height + 7) // 8
    packed = bytearray(packed_size)

    for i, pixel in enumerate(pixels):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)  # MSB first

        # Dithered output is 0 (black) or 255 (white); white -> bit 1.
        if pixel:
            packed[byte_idx] |= 1 << bit_idx

    return bytes(packed)


def convert_to_2bit_planes(image: Image.Image) -> bytes:
    """
    Convert grayscale image to 2-bit format with two separate 1-bit planes.

    The output format is two concatenated 1-bit planes:
    - First plane (MSB): Written to EPD register 0x24
    - Second plane (LSB): Written to EPD register 0x26

    2-bit grayscale levels (for typical e-Ink displays):
    - 0b00 (0): Black
    - 0b01 (1): Dark gray
    - 0b10 (2): Light gray
    - 0b11 (3): White

    Args:
        image: PIL grayscale image.

    Returns:
        Two concatenated 1-bit planes (MSB plane first, then LSB plane).
    """
    width, height = image.size
    pixels = _get_pixel_data(image)

    # Calculate plane size (8 pixels per byte, each plane)
    plane_size = (width * height + 7) // 8
    msb_plane = bytearray(plane_size)
    lsb_plane = bytearray(plane_size)

    for i, pixel in enumerate(pixels):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)  # MSB first

        # Quantize 8-bit to 2-bit (4 levels: 0, 1, 2, 3)
        level = quantize_to_levels(pixel, 8, 2)

        # Extract MSB and LSB of the 2-bit value
        msb = (level >> 1) & 1
        lsb = level & 1

        if msb:
            msb_plane[byte_idx] |= 1 << bit_idx
        if lsb:
            lsb_plane[byte_idx] |= 1 << bit_idx

    # Concatenate: MSB plane first, then LSB plane
    return bytes(msb_plane) + bytes(lsb_plane)


def convert_to_4bit_packed(image: Image.Image) -> bytes:
    """
    Convert grayscale image to 4-bit packed format.

    Each byte contains 2 packed pixels (high nibble = first pixel).

    Args:
        image: PIL grayscale image.

    Returns:
        Packed 4-bit framebuffer data.
    """
    width, height = image.size
    pixels = _get_pixel_data(image)

    # Calculate packed size (2 pixels per byte)
    packed_size = (width * height + 1) // 2
    packed = bytearray(packed_size)

    for i, pixel in enumerate(pixels):
        byte_idx = i // 2

        # Quantize 8-bit to 4-bit (16 levels)
        level = quantize_to_levels(pixel, 8, 4)

        if i % 2 == 0:
            # High nibble (first pixel in byte)
            packed[byte_idx] = level << 4
        else:
            # Low nibble (second pixel in byte)
            packed[byte_idx] |= level

    return bytes(packed)


def convert_png_to_framebuffer(
    png_data: bytes,
    target_bit_depth: int,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> Tuple[bytes, str]:
    """
    Convert PNG image data to raw framebuffer format for a given bit depth.

    Args:
        png_data: Raw PNG image data from HLSS.
        target_bit_depth: Target display bit depth (1, 2, 4, or 8).
        expected_width: Expected display width (for validation).
        expected_height: Expected display height (for validation).

    Returns:
        Tuple of (framebuffer_data, media_type).

    Raises:
        ValueError: If conversion fails or dimensions mismatch.
    """
    try:
        image, width, height = png_to_grayscale(png_data)
    except Exception as e:
        logger.error(f"Failed to load PNG data: {e}")
        raise ValueError(f"Invalid PNG data: {e}")

    # Validate dimensions if provided
    if expected_width and expected_height:
        if width != expected_width or height != expected_height:
            # Resize if dimensions don't match
            logger.warning(
                f"Frame size {width}x{height} doesn't match display "
                f"{expected_width}x{expected_height}, resizing"
            )
            image = image.resize(
                (expected_width, expected_height), Image.Resampling.LANCZOS
            )
            width, height = expected_width, expected_height

    if target_bit_depth == 1:
        data = convert_to_1bit_packed(image)
        return data, "application/octet-stream"

    elif target_bit_depth == 2:
        data = convert_to_2bit_planes(image)
        return data, "application/octet-stream"

    elif target_bit_depth == 4:
        data = convert_to_4bit_packed(image)
        return data, "application/octet-stream"

    elif target_bit_depth == 8:
        # Return raw grayscale bytes (1 byte per pixel)
        data = bytes(_get_pixel_data(image))
        return data, "application/octet-stream"

    else:
        raise ValueError(f"Unsupported bit depth: {target_bit_depth}")


def convert_to_quantized_png(image: Image.Image, target_bit_depth: int) -> bytes:
    """
    Convert grayscale image to a quantized PNG for the target bit depth.

    - bit_depth=1: 1-bit grayscale PNG (threshold at 128)
    - bit_depth=2: 8-bit grayscale PNG quantized to 4 levels (0, 85, 170, 255)
    - bit_depth=4: 8-bit grayscale PNG quantized to 16 levels

    Args:
        image: PIL grayscale image.
        target_bit_depth: Target bit depth (1, 2, or 4).

    Returns:
        PNG image data as bytes.
    """
    if target_bit_depth == 1:
        # Threshold at 128, save as 1-bit PNG
        quantized = image.point(lambda p: 255 if p >= 128 else 0).convert("1")
    elif target_bit_depth in (2, 4):
        levels = 1 << target_bit_depth  # 4 or 16
        max_level = levels - 1
        quantized = image.point(
            lambda p: round(round(p * max_level / 255) * 255 / max_level)
        )
    else:
        quantized = image

    buf = io.BytesIO()
    quantized.save(buf, format="PNG")
    return buf.getvalue()


def convert_png_to_quantized_png(
    png_data: bytes,
    target_bit_depth: int,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> bytes:
    """
    Convert PNG image data to a quantized PNG appropriate for the given bit depth.

    - bit_depth=1: 1-bit grayscale PNG (threshold at 128)
    - bit_depth=2: 8-bit grayscale PNG quantized to 4 levels (0, 85, 170, 255)
    - bit_depth=4: 8-bit grayscale PNG quantized to 16 levels
    - bit_depth>4: returned as-is (no conversion)

    Args:
        png_data: Raw PNG image data from HLSS.
        target_bit_depth: Target display bit depth (1, 2, 4, or 8+).
        expected_width: Expected display width (for validation/resize).
        expected_height: Expected display height (for validation/resize).

    Returns:
        PNG image data as bytes.

    Raises:
        ValueError: If conversion fails.
    """
    if target_bit_depth > 4:
        return png_data

    try:
        image, width, height = png_to_grayscale(png_data)
    except Exception as e:
        logger.error(f"Failed to load PNG data: {e}")
        raise ValueError(f"Invalid PNG data: {e}")

    if expected_width and expected_height:
        if width != expected_width or height != expected_height:
            logger.warning(
                f"Frame size {width}x{height} doesn't match display "
                f"{expected_width}x{expected_height}, resizing"
            )
            image = image.resize(
                (expected_width, expected_height), Image.Resampling.LANCZOS
            )

    return convert_to_quantized_png(image, target_bit_depth)


def get_expected_framebuffer_size(width: int, height: int, bit_depth: int) -> int:
    """
    Calculate the expected framebuffer size for given dimensions and bit depth.

    Args:
        width: Display width in pixels.
        height: Display height in pixels.
        bit_depth: Display bit depth.

    Returns:
        Expected framebuffer size in bytes.
    """
    total_pixels = width * height

    if bit_depth == 1:
        return (total_pixels + 7) // 8
    elif bit_depth == 2:
        # Two 1-bit planes
        return ((total_pixels + 7) // 8) * 2
    elif bit_depth == 4:
        return (total_pixels + 1) // 2
    elif bit_depth == 8:
        return total_pixels
    else:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")


# ---------------------------------------------------------------------------
# Deterministic frame self-test pattern (TEMPORARY debugging aid).
#
# Served when the device requests ?raw=true&pattern=1 (firmware build with
# CONFIG_LLSS_PATTERN_TEST=y). The byte stream MUST stay identical to the C
# implementation in firmware src/pattern_check.c (pattern_expected_byte):
# integer-only math, MSB-first packing, bit 1 = white.
# ---------------------------------------------------------------------------
def _pattern_pixel(x: int, y: int, width: int, height: int) -> int:
    """1 = white, 0 = black. Keep in lockstep with C pattern_pixel()."""
    if x == 0 or x == width - 1 or y == 0 or y == height - 1:
        return 1  # border
    if x < 64 and y < 64:
        return 1  # solid top-left square
    if y < 24:
        return 1  # thick top stripe
    if y == (x * (height - 1)) // (width - 1):
        return 1  # TL->BR diagonal
    if (y % 40) == 0:
        return 1  # horizontal ruler ticks
    return 0


def pattern_framebuffer_1bpp(width: int = 800, height: int = 480) -> bytes:
    """
    Generate the deterministic 1bpp packed self-test pattern.

    MSB = leftmost pixel, bit 1 = white. Output is (width//8)*height bytes
    (48000 for 800x480), matching convert_to_1bit_packed()'s contract.
    """
    stride = width // 8
    packed = bytearray(stride * height)

    for y in range(height):
        for b in range(stride):
            v = 0
            for k in range(8):
                x = b * 8 + k
                if _pattern_pixel(x, y, width, height):
                    v |= 1 << (7 - k)
            packed[y * stride + b] = v

    return bytes(packed)
