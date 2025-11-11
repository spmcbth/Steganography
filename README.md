# 🔐 Image Steganography with AES Encryption

This project demonstrates **LSB image steganography** using **Pixel Location Sequence (PLS)** combined with **AES encryption**.  
It provides a Gradio-based user interface with multiple features for encoding/decoding secret messages inside images, and analyzing results.

---

## ✨ Features
- **Generate AES Key**: Create a new AES key for encryption/decryption.
- **Encode Message**: Hide a secret message inside an image using LSB + AES + PLS.
- **Decode Message**: Extract hidden message from stego image with AES key.
- **Histogram Analysis**: Compare grayscale histograms of original vs. stego images.
- **MSE & PSNR Analysis**: Calculate similarity metrics between original and stego images.

---

## 🚀 How to Run
1. **Clone repository** 
   ```bash
   git clone https://github.com/spmcbth/Steganography.git
   cd Steganography
   ```
2. **Install requirements**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run application**
   ```bash
   python main.py
   ```

4. **The Gradio app will run locally at:** http://127.0.0.1:7860

## 🚀 Run without GUI
- You can test the steganography functions without opening the Gradio interface using `test.py`
   ```bash
   python test.py
   ```
- To configure your test in test.py:
   ```bash
   if __name__ == "__main__":
      orig_file = "image/lena.png"  # Replace with your image path
      message = "This is a secret message. Only those with the key can read it."  # Replace with your test message
      run_comparison(orig_file, message)
   ```
## 💡 Recommendations
- **Use PNG images** to avoid data loss from compression.  
- **Use larger images** to hide longer messages with minimal impact on quality.