import sys
import time
import os
from PIL import Image
import numpy as np
from crypto_utils import generate_aes_key
from stego_utils import encode_lsb, decode_lsb

def calc_metrics(original_path, stego_path):
    """Tính MSE, PSNR để đánh giá chất lượng"""
    orig = np.array(Image.open(original_path).convert("RGB"), dtype=np.float64)
    stego = np.array(Image.open(stego_path).convert("RGB"), dtype=np.float64)
    mse = np.mean((orig - stego) ** 2)
    psnr = float("inf") if mse == 0 else 20 * np.log10(255.0 / np.sqrt(mse))
    return mse, psnr


def run_test(image_path, message):
    print("\n" + "="*70)
    print("🧪 TEST STEGANOGRAPHY (Seeded PLS)")
    print("="*70)
    key = generate_aes_key()
    print(f"🔑 AES Key: {key.hex()[:32]}...")
    print(f"💬 Message: {message[:50]}{'...' if len(message) > 50 else ''}")

    stego_file = "output/stego_output.png"
    pls_file = "output/metadata.enc"

    try:
        print("   🔄 Encoding...", end=" ", flush=True)
        start = time.time()
        encode_lsb(image_path, message, stego_file, pls_file, key, use_seeded_pls=True)
        enc_time = time.time() - start
        print(f"✅ Done ({enc_time:.3f}s)")

        print("   🔄 Decoding...", end=" ", flush=True)
        start = time.time()
        decoded = decode_lsb(stego_file, pls_file, key)
        dec_time = time.time() - start
        print(f"✅ Done ({dec_time:.3f}s)")

        success = decoded == message
        mse, psnr = calc_metrics(image_path, stego_file)

        print(f"\n   📊 RESULT:")
        print(f"      Message OK: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"      MSE: {mse:.6f}")
        print(f"      PSNR: {psnr:.2f} dB")
        if success:
            print(f"\n   ✨ Decoded message: {decoded[:100]}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python test.py <image.png> [message]")
        sys.exit(1)

    image_path = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else "Hello from steganography test!"
    run_test(image_path, message)
