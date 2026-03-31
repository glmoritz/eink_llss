"""
Tests for frame_converter module.

Tests the conversion of PNG frames to various bit depth framebuffer formats.
"""

import io

import pytest
from PIL import Image

from frame_converter import (
    convert_png_to_framebuffer,
    convert_to_1bit_packed,
    convert_to_2bit_planes,
    convert_to_4bit_packed,
    get_expected_framebuffer_size,
    png_to_grayscale,
    quantize_to_levels,
)


def create_test_png(width: int, height: int, pixels: list[int]) -> bytes:
    """Create a test PNG image from a list of grayscale pixel values."""
    img = Image.new("L", (width, height))
    img.putdata(pixels)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestQuantization:
    """Tests for quantize_to_levels function."""

    def test_8bit_to_1bit(self):
        """Test 8-bit to 1-bit quantization."""
        assert quantize_to_levels(0, 8, 1) == 0
        assert quantize_to_levels(127, 8, 1) == 0
        assert quantize_to_levels(128, 8, 1) == 1
        assert quantize_to_levels(255, 8, 1) == 1

    def test_8bit_to_2bit(self):
        """Test 8-bit to 2-bit quantization."""
        assert quantize_to_levels(0, 8, 2) == 0
        assert quantize_to_levels(64, 8, 2) == 1
        assert quantize_to_levels(128, 8, 2) == 2
        assert quantize_to_levels(255, 8, 2) == 3

    def test_8bit_to_4bit(self):
        """Test 8-bit to 4-bit quantization."""
        assert quantize_to_levels(0, 8, 4) == 0
        assert quantize_to_levels(255, 8, 4) == 15
        # Mid values
        assert quantize_to_levels(128, 8, 4) == 8


class TestConvertTo1BitPacked:
    """Tests for 1-bit packed conversion."""

    def test_all_black(self):
        """Test conversion of all-black image."""
        img = Image.new("L", (8, 1))
        img.putdata([0] * 8)
        result = convert_to_1bit_packed(img)
        assert result == bytes([0b00000000])

    def test_all_white(self):
        """Test conversion of all-white image."""
        img = Image.new("L", (8, 1))
        img.putdata([255] * 8)
        result = convert_to_1bit_packed(img)
        assert result == bytes([0b11111111])

    def test_alternating(self):
        """Test conversion of alternating black/white pattern."""
        img = Image.new("L", (8, 1))
        img.putdata([0, 255, 0, 255, 0, 255, 0, 255])
        result = convert_to_1bit_packed(img)
        assert result == bytes([0b01010101])

    def test_msb_first(self):
        """Test that MSB comes first (leftmost pixel in MSB)."""
        img = Image.new("L", (8, 1))
        # First pixel (MSB) is white, rest are black
        img.putdata([255, 0, 0, 0, 0, 0, 0, 0])
        result = convert_to_1bit_packed(img)
        assert result == bytes([0b10000000])


class TestConvertTo2BitPlanes:
    """Tests for 2-bit plane conversion."""

    def test_basic_levels(self):
        """Test conversion covers all 4 levels."""
        img = Image.new("L", (8, 1))
        # 8 pixels with values that map to levels 0, 1, 2, 3
        img.putdata([0, 64, 128, 255, 0, 85, 170, 255])
        result = convert_to_2bit_planes(img)

        # Should be 2 bytes (1 byte MSB plane, 1 byte LSB plane)
        assert len(result) == 2

        # Verify by decoding
        msb_plane = result[0]
        lsb_plane = result[1]

        # Check first 4 pixels
        # Pixel 0: value=0 -> level=0 (MSB=0, LSB=0)
        assert (msb_plane >> 7) & 1 == 0
        assert (lsb_plane >> 7) & 1 == 0

        # Pixel 1: value=64 -> level=1 (MSB=0, LSB=1)
        assert (msb_plane >> 6) & 1 == 0
        assert (lsb_plane >> 6) & 1 == 1

        # Pixel 2: value=128 -> level=2 (MSB=1, LSB=0)
        assert (msb_plane >> 5) & 1 == 1
        assert (lsb_plane >> 5) & 1 == 0

        # Pixel 3: value=255 -> level=3 (MSB=1, LSB=1)
        assert (msb_plane >> 4) & 1 == 1
        assert (lsb_plane >> 4) & 1 == 1

    def test_plane_sizes(self):
        """Test that plane sizes are correct for various image sizes."""
        for width, height in [(8, 1), (16, 16), (800, 480)]:
            img = Image.new("L", (width, height))
            img.putdata([128] * (width * height))
            result = convert_to_2bit_planes(img)

            expected_plane_size = (width * height + 7) // 8
            assert len(result) == expected_plane_size * 2


class TestConvertTo4BitPacked:
    """Tests for 4-bit packed conversion."""

    def test_basic(self):
        """Test basic 4-bit conversion."""
        img = Image.new("L", (2, 1))
        img.putdata([0, 255])
        result = convert_to_4bit_packed(img)

        # 2 pixels = 1 byte
        assert len(result) == 1
        # First pixel (high nibble) = 0, second pixel (low nibble) = 15
        assert result[0] == 0x0F

    def test_mid_values(self):
        """Test mid-range values."""
        img = Image.new("L", (2, 1))
        img.putdata([128, 64])
        result = convert_to_4bit_packed(img)

        # 128 -> ~8, 64 -> ~4
        assert len(result) == 1
        high_nibble = (result[0] >> 4) & 0xF
        low_nibble = result[0] & 0xF
        assert high_nibble == 8  # 128/255 * 15 ≈ 8
        assert low_nibble == 4  # 64/255 * 15 ≈ 4


class TestConvertPngToFramebuffer:
    """Tests for the main PNG to framebuffer conversion function."""

    def test_1bit_conversion(self):
        """Test PNG to 1-bit framebuffer."""
        png = create_test_png(8, 1, [0, 255] * 4)
        data, media_type = convert_png_to_framebuffer(png, 1)

        assert media_type == "application/octet-stream"
        assert len(data) == 1  # 8 pixels / 8 = 1 byte

    def test_2bit_conversion(self):
        """Test PNG to 2-bit framebuffer."""
        png = create_test_png(8, 1, [0, 64, 128, 255] * 2)
        data, media_type = convert_png_to_framebuffer(png, 2)

        assert media_type == "application/octet-stream"
        assert len(data) == 2  # 2 planes of 1 byte each

    def test_4bit_conversion(self):
        """Test PNG to 4-bit framebuffer."""
        png = create_test_png(4, 1, [0, 85, 170, 255])
        data, media_type = convert_png_to_framebuffer(png, 4)

        assert media_type == "application/octet-stream"
        assert len(data) == 2  # 4 pixels / 2 = 2 bytes

    def test_8bit_conversion(self):
        """Test PNG to 8-bit framebuffer."""
        png = create_test_png(4, 1, [10, 20, 30, 40])
        data, media_type = convert_png_to_framebuffer(png, 8)

        assert media_type == "application/octet-stream"
        assert len(data) == 4  # 4 pixels * 1 byte each
        assert list(data) == [10, 20, 30, 40]

    def test_invalid_bit_depth(self):
        """Test that invalid bit depth raises error."""
        png = create_test_png(8, 1, [0] * 8)

        with pytest.raises(ValueError, match="Unsupported bit depth"):
            convert_png_to_framebuffer(png, 5)

    def test_resize_on_dimension_mismatch(self):
        """Test that images are resized when dimensions don't match."""
        # Create 4x4 image but request 8x8
        png = create_test_png(4, 4, [128] * 16)
        data, _ = convert_png_to_framebuffer(
            png, 1, expected_width=8, expected_height=8
        )

        # Should get 8x8 = 64 pixels / 8 = 8 bytes
        assert len(data) == 8


class TestGetExpectedFramebufferSize:
    """Tests for framebuffer size calculation."""

    def test_1bit_size(self):
        """Test 1-bit framebuffer size calculation."""
        # 800x480 = 384000 pixels / 8 = 48000 bytes
        assert get_expected_framebuffer_size(800, 480, 1) == 48000
        # 100x100 = 10000 pixels / 8 = 1250 bytes
        assert get_expected_framebuffer_size(100, 100, 1) == 1250

    def test_2bit_size(self):
        """Test 2-bit framebuffer size calculation."""
        # 800x480 = 384000 pixels / 8 * 2 planes = 96000 bytes
        assert get_expected_framebuffer_size(800, 480, 2) == 96000

    def test_4bit_size(self):
        """Test 4-bit framebuffer size calculation."""
        # 800x480 = 384000 pixels / 2 = 192000 bytes
        assert get_expected_framebuffer_size(800, 480, 4) == 192000

    def test_8bit_size(self):
        """Test 8-bit framebuffer size calculation."""
        # 800x480 = 384000 bytes
        assert get_expected_framebuffer_size(800, 480, 8) == 384000

    def test_invalid_bit_depth(self):
        """Test that invalid bit depth raises error."""
        with pytest.raises(ValueError, match="Unsupported bit depth"):
            get_expected_framebuffer_size(100, 100, 3)
