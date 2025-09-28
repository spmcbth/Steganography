import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# ===== AES Key Management =====
def generate_aes_key(length: int = 32) -> bytes:
    """Sinh AES key (32 bytes = AES-256)."""
    return os.urandom(length)

def save_key(key: bytes, key_file: str):
    """Lưu key dưới dạng hex vào file txt."""
    with open(key_file, "w") as f:
        f.write(key.hex())

def load_key(key_file: str) -> bytes:
    """Đọc key từ file txt."""
    with open(key_file, "r") as f:
        content = f.read().strip()
        return bytes.fromhex(content)

# ===== AES Encryption/Decryption =====
def aes_encrypt(data: bytes, key: bytes) -> bytes:
    """Mã hóa data bằng AES-CBC + PKCS7. Trả về IV + ciphertext."""
    iv = os.urandom(16)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return iv + encrypted

def aes_decrypt(encrypted_data: bytes, key: bytes) -> bytes:
    """Giải mã AES-CBC. Input = IV + ciphertext."""
    iv = encrypted_data[:16]
    encrypted = encrypted_data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(decrypted_padded) + unpadder.finalize()