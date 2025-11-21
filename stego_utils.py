from PIL import Image
import numpy as np
import random
import hashlib
import math
from crypto_utils import aes_encrypt, aes_decrypt

LENGTH_BITS = 16

def generate_pls_seeded(total_pixels: int, needed_bits: int, key: bytes, offset: int = 0) -> list[int]:
    """
    PLS dựa trên key cho Advanced mode.
    Trả về danh sách needed_bits vị trí (pixel_index, channel_index).
    """
    # Tính số pixel cần thiết
    needed_pixels = math.ceil(needed_bits / 3)
    
    if needed_pixels > (total_pixels - offset):
        raise ValueError(f"Not enough pixels: need {needed_pixels}, available {total_pixels - offset}")
    
    # Tạo seed từ key
    seed = int(hashlib.sha256(key).hexdigest(), 16) % (2**32)
    random.seed(seed)
    
    # Tạo mảng pixel từ offset
    arr = list(range(offset, total_pixels))
    
    # Fisher-Yates shuffle: shuffle đúng needed_pixels phần tử cuối
    for i in range(len(arr)-1, len(arr)-needed_pixels-1, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    
    # Lấy needed_pixels cuối và expand ra 3 channels
    selected_pixels = arr[len(arr)-needed_pixels:]
    result = []
    for px in selected_pixels:
        for ch in range(3):  # R, G, B
            result.append(px)
            if len(result) >= needed_bits:
                return result
    
    return result

def generate_pls(total_pixels: int, needed_bits: int) -> list[int]:
    """Random PLS cho Simple mode."""
    needed_pixels = math.ceil(needed_bits / 3)
    
    if needed_pixels > total_pixels:
        raise ValueError(f"Not enough pixels: need {needed_pixels}, available {total_pixels}")
    
    arr = list(range(total_pixels))
    
    # Fisher-Yates shuffle
    for i in range(len(arr)-1, len(arr)-needed_pixels-1, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    
    # Expand pixels to channels
    selected_pixels = arr[len(arr)-needed_pixels:]
    result = []
    for px in selected_pixels:
        for ch in range(3):
            result.append(px)
            if len(result) >= needed_bits:
                return result
    
    return result

def lsb_match(value, bit):
    """LSB matching: thay đổi value ±1 nếu LSB không khớp."""
    bit = int(bit)
    if (value & 1) == bit:
        return value
    if value == 255: 
        return 254
    if value == 0: 
        return 1
    return value + random.choice([-1, 1])

def embed_metadata(im, metadata: bytes, key: bytes) -> int:
    """
    Nhúng metadata vào header của ảnh (Advanced mode).
    Trả về số pixel đã dùng.
    """
    # Mã hóa metadata
    encrypted_metadata = aes_encrypt(metadata, key)
    len_enc = len(encrypted_metadata)
    
    # Kiểm tra giới hạn
    if len_enc > (2 ** LENGTH_BITS) - 1:
        raise ValueError(f"Metadata too large: {len_enc} bytes (max {2**LENGTH_BITS - 1})")
    
    # Tạo bitstream: LENGTH (16 bits) + encrypted_metadata
    length_bitstream = format(len_enc, f'0{LENGTH_BITS}b')
    meta_bitstream = "".join(format(b, "08b") for b in encrypted_metadata)
    bitstream = length_bitstream + meta_bitstream
    
    total_bits = len(bitstream)
    header_pixels = math.ceil(total_bits / 3)
    
    # Kiểm tra ảnh đủ lớn
    width, height = im.size
    if header_pixels > width * height:
        raise ValueError(f"Image too small: need {header_pixels} pixels for metadata")
    
    # Nhúng vào ảnh
    pixels = im.load()
    idx = 0
    
    for px_idx in range(header_pixels):
        row, col = divmod(px_idx, width)
        r, g, b = pixels[col, row]
        
        # Nhúng 3 bits vào R, G, B
        for ch in range(3):
            if idx >= total_bits:
                break
            bit = bitstream[idx]
            
            if ch == 0:
                r = lsb_match(r, bit)
            elif ch == 1:
                g = lsb_match(g, bit)
            else:
                b = lsb_match(b, bit)
            idx += 1
        
        pixels[col, row] = (r, g, b)
    
    return header_pixels

def extract_metadata(im, key: bytes) -> tuple[bytes, int]:
    """
    Trích xuất metadata từ header (Advanced mode).
    Trả về (metadata, số_pixel_đã_dùng).
    """
    pixels = im.load()
    width, height = im.size
    
    # Đọc LENGTH_BITS đầu tiên để biết độ dài metadata
    length_pixels = math.ceil(LENGTH_BITS / 3)
    bitstream = ""
    
    for px_idx in range(length_pixels):
        row, col = divmod(px_idx, width)
        r, g, b = pixels[col, row]
        bitstream += str(r & 1) + str(g & 1) + str(b & 1)
    
    len_enc = int(bitstream[:LENGTH_BITS], 2)
    
    # Tính tổng số bits cần đọc
    total_bits = LENGTH_BITS + len_enc * 8
    header_pixels = math.ceil(total_bits / 3)
    
    # Đọc lại toàn bộ header
    bitstream = ""
    for px_idx in range(header_pixels):
        row, col = divmod(px_idx, width)
        r, g, b = pixels[col, row]
        bitstream += str(r & 1) + str(g & 1) + str(b & 1)
    
    # Parse encrypted metadata
    encrypted_bytes = bytearray()
    bit_pos = LENGTH_BITS
    
    for _ in range(len_enc):
        byte_bits = bitstream[bit_pos:bit_pos + 8]
        if len(byte_bits) < 8:
            raise ValueError("Incomplete metadata in header")
        encrypted_bytes.append(int(byte_bits, 2))
        bit_pos += 8
    
    # Giải mã
    metadata = aes_decrypt(bytes(encrypted_bytes), key)
    return metadata, header_pixels

def encode_lsb(image_path: str, message: str, stego_path: str, pls_enc_path: str, key: bytes, mode: str="simple"):
    """
    Nhúng message vào ảnh.
    
    Simple mode: cần pls_enc_path để lưu PLS
    Advanced mode: pls_enc_path = None, PLS sinh từ key
    """
    im = Image.open(image_path)
    if im.mode != "RGB": 
        im = im.convert("RGB")
    
    width, height = im.size
    total_pixels = width * height
    
    # Mã hóa message
    encrypted_msg = aes_encrypt(message.encode(), key)
    bitstream = "".join(format(b, "08b") for b in encrypted_msg)
    needed_bits = len(bitstream)
    
    offset = 0
    mode = mode.lower()
    
    if mode == "advanced":
        # Nhúng metadata vào header
        metadata = f"advanced:{len(encrypted_msg)}".encode()
        offset = embed_metadata(im, metadata, key)
        print(f"[Advanced] Metadata embedded in {offset} pixels")
        
        # Sinh PLS từ key
        pls = generate_pls_seeded(total_pixels, needed_bits, key, offset)
        
    elif mode == "simple":
        # PLS ngẫu nhiên
        pls = generate_pls(total_pixels, needed_bits)
        
    else:
        raise ValueError(f"Invalid mode: {mode}")
    
    # Nhúng message vào ảnh
    pixels = im.load()
    
    for i, bit in enumerate(bitstream):
        px_idx = pls[i]
        row, col = divmod(px_idx, width)
        r, g, b = pixels[col, row]
        
        ch = i % 3
        bval = int(bit)
        
        if ch == 0:
            r = lsb_match(r, bval)
        elif ch == 1:
            g = lsb_match(g, bval)
        else:
            b = lsb_match(b, bval)
        
        pixels[col, row] = (r, g, b)
    
    # Lưu ảnh
    im.save(stego_path)
    print(f"[{mode.upper()}] Stego image saved: {stego_path}")
    
    # Simple mode: lưu PLS
    if mode == "simple" and pls_enc_path:
        pls_bytes = ",".join(map(str, pls)).encode()
        enc_pls = aes_encrypt(pls_bytes, key)
        with open(pls_enc_path, "wb") as f: 
            f.write(enc_pls)
        print(f"[SIMPLE] PLS saved: {pls_enc_path}")

def decode_lsb(stego_path: str, pls_enc_path: str, key: bytes) -> str:
    """
    Trích xuất message từ ảnh stego.
    
    Simple mode: cần pls_enc_path
    Advanced mode: pls_enc_path = None
    """
    im = Image.open(stego_path)
    if im.mode != "RGB": 
        im = im.convert("RGB")
    
    width, height = im.size
    total_pixels = width * height
    
    if not pls_enc_path:
        # Advanced mode: đọc metadata từ header
        metadata, header_pixels = extract_metadata(im, key)
        metadata_str = metadata.decode(errors="ignore")
        
        if not metadata_str.startswith("advanced:"):
            raise ValueError(f"Invalid metadata format: {metadata_str}")
        
        n_bytes = int(metadata_str.split(":")[1])
        print(f"[Advanced] Metadata: {n_bytes} bytes, header: {header_pixels} pixels")
        
        # Sinh lại PLS từ key
        pls = generate_pls_seeded(total_pixels, n_bytes * 8, key, header_pixels)
        
    else:
        # Simple mode: đọc PLS từ file
        with open(pls_enc_path, "rb") as f: 
            encrypted_data = f.read()
        decrypted_data = aes_decrypt(encrypted_data, key)
        pls = list(map(int, decrypted_data.decode().split(",")))
        print(f"[Simple] PLS loaded: {len(pls)} bits")
    
    # Trích xuất bits
    pixels = im.load()
    bitstream = ""
    
    for i, px_idx in enumerate(pls):
        row, col = divmod(px_idx, width)
        r, g, b = pixels[col, row]
        
        ch = i % 3
        if ch == 0: 
            bitstream += str(r & 1)
        elif ch == 1: 
            bitstream += str(g & 1)
        else: 
            bitstream += str(b & 1)
    
    # Parse bytes
    encrypted_bytes = bytearray()
    for i in range(0, len(bitstream), 8):
        byte_bits = bitstream[i:i+8]
        if len(byte_bits) < 8: 
            break
        encrypted_bytes.append(int(byte_bits, 2))
    
    # Giải mã
    return aes_decrypt(bytes(encrypted_bytes), key).decode()