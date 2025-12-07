# 🔐 Image Steganography with AES Encryption

This project implements an **image steganography system** based on **Least Significant Bit (LSB)** technique combined with **AES-256 encryption** and **Pixel Location Sequence (PLS)**.  

A full-featured **Gradio web interface** is provided to encode, decode, and compare different steganography approaches.

---

## ✨ Features
- Hide secret messages in images using **LSB steganography**
- **AES-256 encryption** before embedding
- Two modes:
  - **Simple Mode**: Random PLS + external encrypted metadata
  - **Advanced Mode**: Seeded PLS + encrypted metadata embedded in image
- Decode hidden messages securely
- Image quality evaluation using **MSE** and **PSNR**
- Histogram comparison (original vs. stego)
- Performance comparison between two methods

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

---

## 💡 Recommendations
- **Use PNG images** to avoid data loss from compression.  
- **Use larger images** to hide longer messages with minimal impact on quality.