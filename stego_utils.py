from PIL import Image
import numpy as np
import random
import hashlib
from crypto_utils import aes_encrypt, aes_decrypt

try:
    from scipy import ndimage
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ===== Helper: Seeded PLS =====
def generate_pls_seeded(total_pixels: int, needed_pixels: int, key: bytes) -> list[int]:
    """Sinh PLS từ key thay vì random thuần túy."""
    if needed_pixels > total_pixels:
        raise ValueError("Not enough pixels to hide the message.")
    seed = int(hashlib.sha256(key).hexdigest(), 16) % (2**32)
    random.seed(seed)
    arr = list(range(total_pixels))
    for i in range(needed_pixels):
        j = random.randint(0, total_pixels - i - 1)
        arr[total_pixels - i - 1], arr[j] = arr[j], arr[total_pixels - i - 1]
    return arr[-needed_pixels:]


def generate_pls(total_pixels: int, needed_pixels: int) -> list[int]:
    """Sinh PLS ngẫu nhiên."""
    if needed_pixels > total_pixels:
        raise ValueError("Not enough pixels to hide the message.")
    arr = list(range(total_pixels))
    for i in range(needed_pixels):
        j = random.randint(0, total_pixels - i - 1)
        arr[total_pixels - i - 1], arr[j] = arr[j], arr[total_pixels - i - 1]
    return arr[-needed_pixels:]


# ===== Helper: Adaptive pixels =====
def get_high_var_pixels(image_path: str, threshold: float = 50.0) -> list[int] | None:
    """Tìm vùng phức tạp bằng Sobel."""
    if not HAS_SCIPY:
        return None
    try:
        im = Image.open(image_path).convert("L")
        arr = np.array(im, dtype=float)
        sobel_x = ndimage.sobel(arr, axis=1)
        sobel_y = ndimage.sobel(arr, axis=0)
        mag = np.sqrt(sobel_x**2 + sobel_y**2)
        rows, cols = np.where(mag > threshold)
        width = arr.shape[1]
        return (rows * width + cols).tolist()
    except Exception:
        return None


def pls_to_bytes(pls: list[int]) -> bytes:
    """Chuyển PLS thành bytes."""
    return ",".join(map(str, pls)).encode()


def bytes_to_pls(data: bytes) -> list[int]:
    """Chuyển bytes thành PLS."""
    return list(map(int, data.decode().split(",")))


# ===== Encode LSB (sửa logic nhúng bit) =====
def encode_lsb(image_path: str, message: str, stego_path: str, pls_enc_path: str,
               key: bytes, use_seeded_pls: bool = True, use_adaptive: bool = False):
    """Giấu message vào ảnh PNG."""
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

    # Sinh PLS
    if use_seeded_pls:
        pls = generate_pls_seeded(total_pixels, needed_pixels, key)
    elif use_adaptive and HAS_SCIPY:
        high_var = get_high_var_pixels(image_path)
        if high_var and len(high_var) >= needed_pixels:
            random.shuffle(high_var)
            pls = high_var[:needed_pixels]
        else:
            pls = generate_pls(total_pixels, needed_pixels)
    else:
        pls = generate_pls(total_pixels, needed_pixels)

    # Nhúng bit
    pixels = im.load()
    for i, bit in enumerate(bitstream):
        x = pls[i]
        row, col = divmod(x, width)
        r, g, b = pixels[col, row]
        channel = i % 3
        if channel == 0:
            r = (r & ~1) | int(bit)
        elif channel == 1:
            g = (g & ~1) | int(bit)
        else:
            b = (b & ~1) | int(bit)
        pixels[col, row] = (r, g, b)

    im.save(stego_path)

    # Metadata (seeded hoặc PLS)
    if use_seeded_pls:
        metadata = f"seeded:{len(encrypted_msg)}".encode()
        encrypted_data = aes_encrypt(metadata, key)
    else:
        pls_bytes = pls_to_bytes(pls)
        encrypted_data = aes_encrypt(pls_bytes, key)

    with open(pls_enc_path, "wb") as f:
        f.write(encrypted_data)


# ===== Decode LSB (sửa logic giải mã) =====
def decode_lsb(stego_path: str, pls_enc_path: str, key: bytes) -> str:
    """Giải mã message từ ảnh PNG."""
    im = Image.open(stego_path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    width, height = im.size
    total_pixels = width * height

    # Giải mã metadata hoặc PLS
    with open(pls_enc_path, "rb") as f:
        encrypted_data = f.read()
    decrypted_data = aes_decrypt(encrypted_data, key)

    try:
        metadata = decrypted_data.decode()
        if metadata.startswith("seeded:"):
            n_bytes = int(metadata.split(":")[1])
            needed_pixels = n_bytes * 8
            pls = generate_pls_seeded(total_pixels, needed_pixels, key)
        else:
            pls = bytes_to_pls(decrypted_data)
    except Exception:
        pls = bytes_to_pls(decrypted_data)

    # Giải mã bitstream
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

    # Chuyển bit → bytes
    encrypted_bytes = bytearray()
    for i in range(0, len(bitstream), 8):
        byte_bits = bitstream[i:i + 8]
        if len(byte_bits) < 8:
            break
        encrypted_bytes.append(int(byte_bits, 2))

    # Giải mã AES
    return aes_decrypt(bytes(encrypted_bytes), key).decode()
