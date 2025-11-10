import sys
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt

def calc_mse_psnr(original, stego):
    orig = np.array(Image.open(original).convert("RGB"), dtype=np.float64)
    stego = np.array(Image.open(stego).convert("RGB"), dtype=np.float64)

    mse = np.mean((orig - stego) ** 2)
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = 20 * np.log10(255.0 / np.sqrt(mse))
    
    return mse, psnr

def plot_hist(original, stego):
    orig_gray = np.array(Image.open(original).convert("L"))
    stego_gray = np.array(Image.open(stego).convert("L"))

    orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0, 255))
    stego_hist, _ = np.histogram(stego_gray.flatten(), bins=256, range=(0, 255))

    x = np.arange(256)
    plt.plot(x, orig_hist, label="Original")
    plt.plot(x, stego_hist, label="Stego", linestyle="--")
    plt.title("Grayscale Histogram Comparison")
    plt.legend()
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stego_eval.py original.png stego.png")
        sys.exit(1)

    orig = sys.argv[1]
    stego = sys.argv[2]

    mse, psnr = calc_mse_psnr(orig, stego)
    print(f"MSE  : {mse:.5f}")
    print(f"PSNR : {psnr:.5f} dB")

    plot_hist(orig, stego)