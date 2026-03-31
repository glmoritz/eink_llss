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

    Each byte contains 8 packed pixels (MSB = leftmost pixel).
    Threshold at 128: values >= 128 become 1 (white), < 128 become 0 (black).

    Args:
        image: PIL grayscale image.

    Returns:
        Packed 1-bit framebuffer data.
    """
    width, height = image.size
    pixels = _get_pixel_data(image)

    # Calculate packed size (8 pixels per byte)
    packed_size = (width * height + 7) // 8
    packed = bytearray(packed_size)

    for i, pixel in enumerate(pixels):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)  # MSB first

        # Threshold: >= 128 is white (1), < 128 is black (0)
        if pixel >= 128:
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


def get_expected_framebuffer_size(
    width: int, height: int, bit_depth: int
) -> int:
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
