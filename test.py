import os
import time
from PIL import Image
import numpy as np
from crypto_utils import generate_aes_key
from stego_utils import encode_lsb, decode_lsb

# ==============================
# Tính MSE/PSNR
# ==============================
def calc_metrics(original_path, stego_path):
    orig = np.array(Image.open(original_path).convert("RGB"), dtype=np.float64)
    stego = np.array(Image.open(stego_path).convert("RGB"), dtype=np.float64)
    mse = np.mean((orig - stego) ** 2)
    psnr = float("inf") if mse == 0 else 20 * np.log10(255.0 / np.sqrt(mse))
    return mse, psnr

# ==============================
# Run test cho 1 mode
# ==============================
def run_mode(image_path, mode, message):
    print("\n" + "="*60)
    print(f"🧪 TEST MODE: {mode.upper()}")
    print("="*60)

    key = generate_aes_key()
    print(f"🔑 AES Key: {key.hex()[:32]}...")
    print(f"💬 Message preview: {message[:50]}{'...' if len(message) > 50 else ''}")

    os.makedirs("output", exist_ok=True)
    stego_file = f"output/stego_{mode}.png"
    pls_file = f"output/metadata_{mode}.enc"

    # Encode
    print("   🔄 Encoding...", end=" ", flush=True)
    start = time.time()
    encode_lsb(image_path, message, stego_file, pls_file, key, mode=mode.lower())
    enc_time = time.time() - start
    print(f"✅ Done ({enc_time:.3f}s)")

    # Decode
    print("   🔄 Decoding...", end=" ", flush=True)
    start = time.time()
    decoded = decode_lsb(stego_file, pls_file, key)
    dec_time = time.time() - start
    print(f"✅ Done ({dec_time:.3f}s)")

    # Metrics
    mse, psnr = calc_metrics(image_path, stego_file)
    success = decoded == message

    print(f"\n   📊 RESULT:")
    print(f"      Message OK: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"      MSE: {mse:.6f}")
    print(f"      PSNR: {psnr:.2f} dB")
    if success:
        print(f"      Decoded message preview: {decoded}")
    print(f"      Encode time: {enc_time:.3f}s, Decode time: {dec_time:.3f}s")

# ==============================
# Main: chạy tất cả 3 mode
# ==============================
if __name__ == "__main__":
    image_path = "image/tokyo.jpg"  # Đảm bảo ảnh 512x512 RGB PNG
    message = ("This is a secret message. Do not share it. Keep it hidden inside the image. "
               "Only those with the key can read it. This is a secret message. This is a secret message. "
               "Make sure it stays invisible to the naked eye.")

    modes = ["simple", "advanced", "adaptive"]
    for mode in modes:
        run_mode(image_path, mode, message)
