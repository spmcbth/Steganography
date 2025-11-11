from PIL import Image
import numpy as np
import random
import hashlib
from crypto_utils import aes_encrypt, aes_decrypt

# ===== Helper: PLS Seeded (Advanced) =====
def generate_pls_seeded(total_pixels: int, needed_pixels: int, key: bytes) -> list[int]:
    """Sinh PLS từ key (advanced) thay vì random thuần túy."""
    if needed_pixels > total_pixels:
        raise ValueError("Not enough pixels to hide the message.")
    seed = int(hashlib.sha256(key).hexdigest(), 16) % (2**32)
    random.seed(seed)
    arr = list(range(total_pixels))
    for i in range(needed_pixels):
        j = random.randint(0, total_pixels - i - 1)
        arr[total_pixels - i - 1], arr[j] = arr[j], arr[total_pixels - i - 1]
    return arr[-needed_pixels:]

# ===== Helper: Random PLS (Simple) =====
def generate_pls(total_pixels: int, needed_pixels: int) -> list[int]:
    """Sinh PLS ngẫu nhiên (simple)."""
    if needed_pixels > total_pixels:
        raise ValueError("Not enough pixels to hide the message.")
    arr = list(range(total_pixels))
    for i in range(needed_pixels):
        j = random.randint(0, total_pixels - i - 1)
        arr[total_pixels - i - 1], arr[j] = arr[j], arr[total_pixels - i - 1]
    return arr[-needed_pixels:]

# ===== Helper: Adaptive pixels (high variance) =====
def generate_pls_adaptive(total_pixels: int, needed_pixels: int) -> list[int]:
    """PLS adaptive: đơn giản dùng shuffle toàn ảnh (bỏ Sobel)."""
    return generate_pls(total_pixels, needed_pixels)

# ===== Helper: Convert PLS ↔ bytes =====
def pls_to_bytes(pls: list[int]) -> bytes:
    return ",".join(map(str, pls)).encode()

def bytes_to_pls(data: bytes) -> list[int]:
    return list(map(int, data.decode().split(",")))

# ===== Helper: LSB Matching =====
def lsb_match(value, bit):
    bit = int(bit)
    if (value & 1) == bit:
        return value
    if value == 255:
        return 254
    if value == 0:
        return 1
    return value + random.choice([-1, 1])

# ===== Encode LSB =====
def encode_lsb(image_path: str, message: str, stego_path: str, pls_enc_path: str,
               key: bytes, mode: str = "simple"):
    """Giấu message vào ảnh PNG với mode: simple / advanced / adaptive."""
    im = Image.open(image_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    width, height = im.size
    total_pixels = width * height

    # Mã hóa message
    encrypted_msg = aes_encrypt(message.encode(), key)
    bitstream = "".join(format(b, "08b") for b in encrypted_msg)
    needed_pixels = len(bitstream)
    if needed_pixels > total_pixels * 3:
        raise ValueError("Message quá lớn cho ảnh này.")

    # Chọn PLS
    mode = mode.lower()
    if mode == "advanced":
        pls = generate_pls_seeded(total_pixels, needed_pixels, key)
    elif mode == "adaptive":
        pls = generate_pls_adaptive(total_pixels, needed_pixels)
    else:  # simple
        pls = generate_pls(total_pixels, needed_pixels)

    # Nhúng bit
    pixels = im.load()
    for i, bit in enumerate(bitstream):
        x = pls[i]
        row, col = divmod(x, width)
        r, g, b = pixels[col, row]
        channel = i % 3
        bit_val = int(bit)
        if channel == 0:
            r = lsb_match(r, bit_val)
        elif channel == 1:
            g = lsb_match(g, bit_val)
        else:
            b = lsb_match(b, bit_val)
        pixels[col, row] = (r, g, b)

    im.save(stego_path)

    # Metadata
    if mode == "advanced":
        metadata = f"advanced:{len(encrypted_msg)}".encode()
        encrypted_data = aes_encrypt(metadata, key)
    else:
        pls_bytes = pls_to_bytes(pls)
        encrypted_data = aes_encrypt(pls_bytes, key)

    with open(pls_enc_path, "wb") as f:
        f.write(encrypted_data)

# ===== Decode LSB =====
def decode_lsb(stego_path: str, pls_enc_path: str, key: bytes) -> str:
    """Giải mã message từ ảnh PNG."""
    im = Image.open(stego_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    width, height = im.size
    total_pixels = width * height

    with open(pls_enc_path, "rb") as f:
        encrypted_data = f.read()
    decrypted_data = aes_decrypt(encrypted_data, key)

    try:
        metadata = decrypted_data.decode()
        if metadata.startswith("advanced:"):
            n_bytes = int(metadata.split(":")[1])
            needed_pixels = n_bytes * 8
            pls = generate_pls_seeded(total_pixels, needed_pixels, key)
        else:
            pls = bytes_to_pls(decrypted_data)
    except Exception:
        pls = bytes_to_pls(decrypted_data)

    pixels = im.load()
    bitstream = ""
    for i, x in enumerate(pls):
        row, col = divmod(x, width)
        r, g, b = pixels[col, row]
        channel = i % 3
        if channel == 0:
            bitstream += str(r & 1)
        elif channel == 1:
            bitstream += str(g & 1)
        else:
            bitstream += str(b & 1)

    encrypted_bytes = bytearray()
    for i in range(0, len(bitstream), 8):
        byte_bits = bitstream[i:i + 8]
        if len(byte_bits) < 8:
            break
        encrypted_bytes.append(int(byte_bits, 2))

    return aes_decrypt(bytes(encrypted_bytes), key).decode()
