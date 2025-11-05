from PIL import Image
import random
from crypto_utils import aes_encrypt, aes_decrypt

# ===== Helper functions for PLS =====
def generate_pls(total_pixels: int, needed_pixels: int) -> list[int]:
    """Sinh Pixel Location Sequence (PLS) ngẫu nhiên."""
    if needed_pixels > total_pixels:
        raise ValueError("Not enough pixels to hide the message.")
    arr = list(range(total_pixels))
    for i in range(needed_pixels):
        j = random.randint(0, total_pixels - i - 1)
        arr[total_pixels - i - 1], arr[j] = arr[j], arr[total_pixels - i - 1]
    return arr[-needed_pixels:]

def pls_to_bytes(pls: list[int]) -> bytes:
    """Chuyển PLS thành bytes."""
    return ",".join(map(str, pls)).encode()

def bytes_to_pls(data: bytes) -> list[int]:
    """Chuyển bytes thành PLS."""
    return list(map(int, data.decode().split(",")))

# ===== Encode LSB =====
def encode_lsb(image_path: str, message: str, stego_path: str, pls_enc_path: str, key: bytes):
    """Giấu message vào ảnh PNG."""
    im = Image.open(image_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    width, height = im.size
    total_pixels = width * height

    # Encrypt message
    encrypted_msg = aes_encrypt(message.encode(), key)
    n_enc = len(encrypted_msg)
    needed_pixels = 3 * n_enc

    # Generate PLS
    pls = generate_pls(total_pixels, needed_pixels)

    # Embed data
    pixels = im.load()
    pls_idx = 0
    for byte in encrypted_msg:
        byte_bin = format(byte, "08b")
        channel_vals = []
        for _ in range(3):
            x = pls[pls_idx]
            row, col = divmod(x, width)
            r, g, b = pixels[col, row]
            channel_vals.extend([r, g, b])
            pls_idx += 1

        # Thay LSB theo bit
        for j, bit in enumerate(byte_bin):
            val = channel_vals[j]
            if (bit == "0" and val % 2 != 0):
                val -= 1
            elif (bit == "1" and val % 2 == 0):
                val = val + 1 if val == 0 else val - 1
            channel_vals[j] = val

        pls_idx -= 3
        for p in range(3):
            x = pls[pls_idx]
            row, col = divmod(x, width)
            r, g, b = channel_vals[p * 3:p * 3 + 3]
            pixels[col, row] = (r, g, b)
            pls_idx += 1

    im.save(stego_path)

    # Encrypt PLS
    pls_bytes = pls_to_bytes(pls)
    encrypted_pls = aes_encrypt(pls_bytes, key)
    with open(pls_enc_path, "wb") as f:
        f.write(encrypted_pls)

# ===== Decode LSB =====
def decode_lsb(stego_path: str, pls_enc_path: str, key: bytes) -> str:
    """Giải mã message từ ảnh PNG."""
    im = Image.open(stego_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    width, height = im.size

    # Decrypt PLS
    with open(pls_enc_path, "rb") as f:
        encrypted_pls = f.read()
    pls_bytes = aes_decrypt(encrypted_pls, key)
    pls = bytes_to_pls(pls_bytes)

    # Extract bytes
    pixels = im.load()
    encrypted_msg = bytearray()
    pls_idx = 0
    while pls_idx < len(pls):
        channel_vals = []
        for _ in range(3):
            x = pls[pls_idx]
            row, col = divmod(x, width)
            r, g, b = pixels[col, row]
            channel_vals.extend([r, g, b])
            pls_idx += 1

        bits = "".join("0" if val % 2 == 0 else "1" for val in channel_vals[:8])
        encrypted_msg.append(int(bits, 2))

    # Decrypt AES
    return aes_decrypt(bytes(encrypted_msg), key).decode()