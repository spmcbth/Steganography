import os
import time
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from crypto_utils import generate_aes_key
from stego_utils import encode_lsb, decode_lsb
import tempfile
import shutil

# Tính MSE/PSNR
def calc_metrics(original_path, stego_path):
    orig = np.array(Image.open(original_path).convert("RGB"), dtype=np.float64)
    stego = np.array(Image.open(stego_path).convert("RGB"), dtype=np.float64)
    mse = np.mean((orig - stego) ** 2)
    psnr = float("inf") if mse == 0 else 20 * np.log10(255.0 / np.sqrt(mse))
    return mse, psnr

def plot_hist_mode(orig_file, stego_file, mode_name, output_path):
    orig_gray = np.array(Image.open(orig_file).convert("L"))
    stego_gray = np.array(Image.open(stego_file).convert("L"))

    orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0,255))   
    stego_hist, _ = np.histogram(stego_gray.flatten(), bins=256, range=(0,255))

    x = np.arange(256)
    fig, ax = plt.subplots(figsize=(10,5))
    ax.plot(x, orig_hist, label="Ảnh gốc", color="blue", linewidth=2)
    ax.plot(x, stego_hist, label=f"{mode_name.capitalize()} (Stego)", color="orange", linestyle="--", linewidth=1.5)
    
    ax.set_title(f"So sánh Histogram - Phương pháp: {mode_name.capitalize()}")
    ax.set_xlabel("Giá trị Pixel")
    ax.set_ylabel("Số lượng")
    ax.set_xlim(0, 255)
    ax.legend()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

def run_comparison(orig_file, message):
    try:
        # Copy image to temp
        tmp_img_path = tempfile.mktemp(suffix=".png")
        shutil.copy(orig_file, tmp_img_path)

        # Get resolution
        with Image.open(tmp_img_path) as im:
            width, height = im.size

        modes = ["simple", "advanced"]
        stego_paths = []
        metrics_text = ""

        for mode in modes:
            key = generate_aes_key()
            tmp_stego_path = tempfile.mktemp(suffix=".png")
            tmp_pls_path = tempfile.mktemp(suffix=".enc") if mode == "simple" else None

            # Encode
            start = time.time()
            encode_lsb(tmp_img_path, message, tmp_stego_path, tmp_pls_path, key, mode=mode)
            enc_time = time.time() - start

            # Decode
            start = time.time()
            decoded = decode_lsb(tmp_stego_path, tmp_pls_path, key)
            dec_time = time.time() - start

            # Metrics
            mse, psnr = calc_metrics(tmp_img_path, tmp_stego_path)

            stego_paths.append(tmp_stego_path)

            metrics_text += f"Resolution: {width}x{height}\n"
            metrics_text += f"Phương pháp: {mode.capitalize()}\n"
            metrics_text += f"   MSE: {mse:.6f}\n"
            metrics_text += f"   PSNR: {psnr:.2f} dB\n"
            metrics_text += f"   Encode time: {enc_time:.3f}s\n"
            metrics_text += f"   Decode time: {dec_time:.3f}s\n"
            metrics_text += f"   Decoded message: {decoded[:100] + '...' if len(decoded) > 100 else decoded}\n\n"

            # Cleanup pls if exists
            if tmp_pls_path:
                os.unlink(tmp_pls_path)

        # Tạo thư mục output nếu chưa có
        os.makedirs("output", exist_ok=True)

        # Lưu kết quả vào file text
        with open("output/comparison_results.txt", "w", encoding="utf-8") as f:
            f.write(metrics_text)

        # Plot histograms
        for mode, stego_path in zip(modes, stego_paths):
            plot_hist_mode(tmp_img_path, stego_path, mode, f"output/histogram_{mode}.png")

        # Combined histogram
        orig_gray = np.array(Image.open(tmp_img_path).convert("L"))
        hist_data = {"Original": np.histogram(orig_gray.flatten(), bins=256, range=(0,255))[0]}

        for mode, stego_path in zip(modes, stego_paths):
            stego_gray = np.array(Image.open(stego_path).convert("L"))
            hist_data[mode.capitalize()] = np.histogram(stego_gray.flatten(), bins=256, range=(0,255))[0]

        x = np.arange(256)
        fig, ax = plt.subplots(figsize=(12,5))
        colors = {"Original": "blue", "Simple": "green", "Advanced": "red"}
        linestyles = {"Original": "-", "Simple": "--", "Advanced": ":"}
        for label, hist in hist_data.items():
            ax.plot(x, hist, label=label, color=colors.get(label, "black"), linestyle=linestyles.get(label, "-"), linewidth=1.5)
        
        ax.set_title("So sánh Histogram - Cả 2 Phương Pháp")
        ax.set_xlabel("Giá trị Pixel")
        ax.set_ylabel("Số lượng")
        ax.set_xlim(0, 255)
        ax.legend()
        plt.savefig("output/histogram_comparison.png", dpi=150, bbox_inches="tight")
        plt.close()

        # Lưu ảnh stego vào thư mục output
        shutil.copy(stego_paths[0], "output/stego_simple.png")
        shutil.copy(stego_paths[1], "output/stego_advanced.png")

        # Cleanup
        os.unlink(tmp_img_path)
        for path in stego_paths:
            os.unlink(path)

    except Exception as e:
        pass

    # Print thông báo hoàn tất
    print("So sánh hoàn tất. Kiểm tra thư mục output/")

if __name__ == "__main__":
    orig_file = "image/cameraman.png"  # Replace with your image path
    message = ("This is a secret message. Only those with the key can read it.")    # Replace with your test message
    run_comparison(orig_file, message)