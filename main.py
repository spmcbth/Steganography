import gradio as gr
import tempfile
from crypto_utils import generate_aes_key, save_key, load_key
from stego_utils import encode_lsb, decode_lsb
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np

# ===== Generate Key =====
def generate_key():
    try:
        key = generate_aes_key()
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", prefix="aes_key_")
        save_key(key, tmp_file.name)
        gr.Info("✅ Key generated successfully! Keep this key safe and never share it publicly.")
        return tmp_file.name
    except Exception as e:
        gr.Error(f"❌ Error generating key: {str(e)}")
        return None

# ===== Encode =====
def encode_message(image_file, message, key_file):
    if not image_file or not message or not key_file:
        gr.Warning("⚠️ Please provide image, message, and key file")
        return None, None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_key, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls:

            with open(image_file, "rb") as f:
                tmp_img.write(f.read())
            with open(key_file, "r") as f:
                tmp_key.write(f.read().encode())

            tmp_img.flush()
            tmp_key.flush()

            key = load_key(tmp_key.name)
            encode_lsb(tmp_img.name, message, tmp_stego.name, tmp_pls.name, key)

            gr.Info("✅ Message encoded successfully!")
            return tmp_stego.name, tmp_pls.name
    except Exception as e:
        gr.Error(f"❌ Error encoding: {str(e)}")
        return None, None

# ===== Decode =====
def decode_message(stego_file, pls_file, key_file):
    if not stego_file or not pls_file or not key_file:
        gr.Warning("⚠️ Please provide all required files")
        return None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_key:

            with open(stego_file, "rb") as f:
                tmp_stego.write(f.read())
            with open(pls_file, "rb") as f:
                tmp_pls.write(f.read())
            with open(key_file, "r") as f:
                tmp_key.write(f.read().encode())

            tmp_stego.flush()
            tmp_pls.flush()
            tmp_key.flush()

            key = load_key(tmp_key.name)
            decoded_message = decode_lsb(tmp_stego.name, tmp_pls.name, key)

            gr.Info("✅ Message decoded successfully!")
            return f"{decoded_message}"
    except Exception as e:
        gr.Error(f"❌ Error decoding: {str(e)}")
        return None

# ===== Histogram =====
def compare_histograms_and_metrics(original_img, stego_img):
    if original_img is None or stego_img is None:
        gr.Warning("⚠️ Please provide both original and stego images")
        return None, None, None
    try:
        orig = Image.open(original_img).convert("RGB")
        stego = Image.open(stego_img).convert("RGB")

        orig_gray = np.array(orig.convert("L"))
        stego_gray = np.array(stego.convert("L"))

        # Histogram
        orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0, 255))
        stego_hist, _ = np.histogram(stego_gray.flatten(), bins=256, range=(0, 255))

        x = np.arange(256)
        fig, ax = plt.subplots(figsize=(10, 4))

        ax.plot(x, orig_hist, label="Original", linewidth=1.5, color="blue")
        ax.plot(x, stego_hist, label="Stego", linewidth=1.5, linestyle="--", color="orange")

        ax.set_title("Grayscale Histogram Comparison")
        ax.set_xlim(0, 255)
        ax.legend()

        temp_plot = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp_plot.name, dpi=150, bbox_inches='tight')
        plt.close()

        # ==== MSE & PSNR ====
        orig_arr = np.array(orig, dtype=np.float64)
        stego_arr = np.array(stego, dtype=np.float64)

        mse = np.mean((orig_arr - stego_arr) ** 2)
        psnr = float("inf") if mse == 0 else 20 * np.log10(255.0 / np.sqrt(mse))

        return temp_plot.name, mse, psnr

    except Exception as e:
        gr.Error(f"❌ Error generating histogram/metrics: {str(e)}")
        return None, None, None

# ===== Interface =====
def create_interface():
    with gr.Blocks(title="Image Steganography with AES", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🔐 Image Steganography with AES Encryption")
        gr.Markdown("Advanced **LSB Steganography** tool using Pixel Location Sequence (PLS) combined with **AES encryption** for secure message hiding.")

        with gr.Tabs():
            with gr.Tab("🔑 Generate Key"):
                with gr.Column():
                    gen_btn = gr.Button("🎲 Generate New AES Key", variant="primary", size="lg")
                    key_download = gr.File(label="📥 Download Generated Key", interactive=False)
                gen_btn.click(fn=generate_key, outputs=[key_download])

            with gr.Tab("🔒 Encode Message"):
                with gr.Row():
                    with gr.Column():
                        encode_image = gr.Image(label="📁 Upload Cover Image", type="filepath", image_mode="RGB", height=250)
                        encode_message_text = gr.Textbox(label="💬 Secret Message", placeholder="Enter your secret message here...", lines=5)
                        encode_key = gr.File(label="🔑 Upload AES Key File (.txt)", file_types=[".txt"])
                        encode_btn = gr.Button("🔒 Encode Message", variant="primary", size="lg")
                    with gr.Column():
                        stego_download = gr.File(label="📥 Download Stego Image", interactive=False)
                        pls_download = gr.File(label="📥 Download Encrypted PLS File", interactive=False)
                encode_btn.click(fn=encode_message, inputs=[encode_image, encode_message_text, encode_key], outputs=[stego_download, pls_download])

            with gr.Tab("🔓 Decode Message"):
                with gr.Row():
                    with gr.Column():
                        decode_stego = gr.Image(label="📁 Upload Stego Image", type="filepath", image_mode="RGB", height=250)
                        decode_pls = gr.File(label="📁 Upload PLS File (.enc)", file_types=[".enc"])
                        decode_key = gr.File(label="🔑 Upload AES Key File (.txt)", file_types=[".txt"])
                        decode_btn = gr.Button("🔓 Decode Message", variant="primary", size="lg")
                    with gr.Column():
                        decoded_output = gr.Textbox(label="📝 Decoded Message", interactive=False, lines=10, placeholder="Decoded message will appear here...")
                decode_btn.click(fn=decode_message, inputs=[decode_stego, decode_pls, decode_key], outputs=[decoded_output])

            with gr.Tab("📊 Image Analysis"):
                gr.Markdown("""
                Compare **original** and **stego** images using:
                - **Histogram Comparison:** Visualize pixel intensity distributions.
                - **MSE (Mean Squared Error):** Measures the average squared difference between original and stego images.
                - **PSNR (Peak Signal-to-Noise Ratio):** Indicates distortion level. Higher PSNR → stego image is closer to the original.
                """)
                with gr.Row():
                    orig_image = gr.Image(label="📁 Original Image", type="filepath", image_mode="RGB", height=250)
                    stego_image = gr.Image(label="📁 Stego Image", type="filepath", image_mode="RGB", height=250)

                compare_btn = gr.Button("🔍 Analyze", variant="secondary")

                comparison_plot = gr.Image(label="Histogram Comparison", type="filepath", height=350)
                mse_output = gr.Number(label="MSE")
                psnr_output = gr.Number(label="PSNR (dB)")

                compare_btn.click(
                    fn=compare_histograms_and_metrics,
                    inputs=[orig_image, stego_image],
                    outputs=[comparison_plot, mse_output, psnr_output]
                )

            with gr.Tab("ℹ️ About Us"):
                gr.Markdown("""
                    This project demonstrates **LSB image steganography** with **Pixel Location Sequence (PLS)** 
                    combined with **AES encryption** for secure and high-capacity message hiding.

                    👨‍💻 **Team Members**: 
                    - Mạch Gia Hân - B2207519
                    - Sơn Nguyễn Mỹ Quyên - B2207558

                    🏫 **University**: Can Tho University  
                    📅 **Year**: 2025
                    """)

        gr.Markdown("---")
        gr.Markdown("💡 **Tips**: When generating a key, keep it safe and **never share it publicly**. Without it, you cannot decode your hidden messages!")
    return app

if __name__ == "__main__":
    app = create_interface()
    app.launch(share=True, debug=True)