import os
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt

# Tính MSE/PSNR
def calc_metrics(original_path, stego_path):
    orig = np.array(Image.open(original_path).convert("RGB"), dtype=np.float64)
    stego = np.array(Image.open(stego_path).convert("RGB"), dtype=np.float64)
    mse = np.mean((orig - stego) ** 2)
    psnr = float("inf") if mse == 0 else 20 * np.log10(255.0 / np.sqrt(mse))
    return mse, psnr

def plot_hist_mode(orig_file, stego_file, mode_name):
    orig_gray = np.array(Image.open(orig_file).convert("L"))
    stego_gray = np.array(Image.open(stego_file).convert("L"))

    orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0,256))   
    stego_hist, _ = np.histogram(stego_gray.flatten(), bins=256, range=(0,256))

    x = np.arange(256)
    plt.figure(figsize=(10,5))
    plt.plot(x, orig_hist, label="Original")
    plt.plot(x, stego_hist, linestyle="--", label=f"Stego ({mode_name})")
    
    plt.title(f"Grayscale Histogram Comparison - Mode: {mode_name}")
    plt.xlabel("Pixel Value")
    plt.ylabel("Count")
    plt.xlim(0, 255)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    orig_file = "image/tokyo.jpg"  # ảnh gốc
    modes = ["simple","advanced","adaptive"]
    stego_files = [f"output/stego_{mode}.png" for mode in modes]

    for mode, stego_file in zip(modes, stego_files):
        if not os.path.exists(stego_file):
            print(f"Stego file not found: {stego_file}")
            continue
        mse, psnr = calc_metrics(orig_file, stego_file)
        print(f"Mode: {mode} | MSE: {mse:.5f} | PSNR: {psnr:.5f} dB")
        plot_hist_mode(orig_file, stego_file, mode)
