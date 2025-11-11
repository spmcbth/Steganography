import gradio as gr
import tempfile
import time
import os
import shutil
from crypto_utils import generate_aes_key, save_key, load_key
from stego_utils import encode_lsb, decode_lsb
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np

# ===== Encode & Decode tự động =====
def auto_encode_decode(image_file, message, mode):
    if not image_file or not message:
        gr.Warning("⚠️ Vui lòng cung cấp ảnh và tin nhắn")
        return None, None, None, None, None, None, None, None
    
    try:
        key = generate_aes_key()
        timestamp = int(time.time())
        stego_filename = f"stego_image_{mode}_{timestamp}.png"
        pls_filename = f"pls_metadata_{mode}_{timestamp}.enc" if mode=="simple" else None
        key_filename = f"aes_key_{mode}_{timestamp}.txt"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_key:

            with open(image_file, "rb") as f:
                tmp_img.write(f.read())
            tmp_img.flush()
            save_key(key, tmp_key.name)
            tmp_key.flush()

            start_enc = time.time()
            encode_lsb(tmp_img.name, message, tmp_stego.name, tmp_pls.name if mode=="simple" else None, key, mode=mode)
            enc_time = time.time() - start_enc

            start_dec = time.time()
            decoded_message = decode_lsb(tmp_stego.name, tmp_pls.name if mode=="simple" else None, key)
            dec_time = time.time() - start_dec

            orig = np.array(Image.open(tmp_img.name).convert("RGB"), dtype=np.float64)
            stego = np.array(Image.open(tmp_stego.name).convert("RGB"), dtype=np.float64)
            mse = np.mean((orig - stego)**2)
            psnr = float("inf") if mse==0 else 20*np.log10(255.0/np.sqrt(mse))

            # Histogram
            orig_gray = np.array(Image.open(tmp_img.name).convert("L"))
            stego_gray = np.array(Image.open(tmp_stego.name).convert("L"))
            orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0,255))
            stego_hist, _ = np.histogram(stego_gray.flatten(), bins=256, range=(0,255))
            x = np.arange(256)
            fig, ax = plt.subplots(figsize=(10,4))
            ax.plot(x, orig_hist, label="Ảnh gốc", color="blue", linewidth=1.5)
            ax.plot(x, stego_hist, label="Ảnh đã mã hóa", color="orange", linestyle="--", linewidth=1.5)
            ax.set_title(f"So sánh Histogram - Chế độ: {mode.upper()}")
            ax.set_xlabel("Giá trị Pixel")
            ax.set_ylabel("Số lượng")
            ax.set_xlim(0,255)
            ax.legend()
            temp_plot = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(temp_plot.name, dpi=150, bbox_inches="tight")
            plt.close()

            tmp_img.close()
            tmp_stego.close()
            if mode=="simple": tmp_pls.close()
            tmp_key.close()

            # Copy ra thư mục tạm
            stego_dir = tempfile.mkdtemp()
            stego_path = os.path.join(stego_dir, stego_filename)
            shutil.copy(tmp_stego.name, stego_path)

            key_dir = tempfile.mkdtemp()
            key_path = os.path.join(key_dir, key_filename)
            shutil.copy(tmp_key.name, key_path)

            pls_path = None
            if mode=="simple":
                pls_dir = tempfile.mkdtemp()
                pls_path = os.path.join(pls_dir, pls_filename)
                shutil.copy(tmp_pls.name, pls_path)

            return (stego_path, pls_path, key_path,
                    decoded_message, f"⏱️ Mã hóa: {enc_time:.3f}s | Giải mã: {dec_time:.3f}s",
                    temp_plot.name, mse, psnr)

    except Exception as e:
        gr.Error(f"❌ Lỗi: {str(e)}")
        return None, None, None, None, None, None, None, None

# ===== Decode Message =====
def decode_message(stego_file, pls_file, key_file, mode):
    if not stego_file or not key_file:
        gr.Warning("⚠️ Cần ảnh stego và khóa AES")
        return None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_key:

            with open(stego_file, "rb") as f: tmp_stego.write(f.read())
            if mode=="simple" and pls_file:
                with open(pls_file, "rb") as f: tmp_pls.write(f.read())
            with open(key_file, "r") as f: tmp_key.write(f.read().encode())

            tmp_stego.flush()
            tmp_pls.flush()
            tmp_key.flush()

            key = load_key(tmp_key.name)
            pls_path = tmp_pls.name if mode=="simple" else None
            decoded_message = decode_lsb(tmp_stego.name, pls_path, key)
            return decoded_message
    except Exception as e:
        gr.Error(f"❌ Lỗi khi giải mã: {str(e)}")
        return None
    
# ===== Run Tests cho 2 mode =====
def run_tests(image_file, message):
    if not image_file or not message:
        gr.Warning("⚠️ Vui lòng cung cấp ảnh và tin nhắn")
        return None, "Không có kết quả"
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
            with open(image_file, "rb") as f:
                tmp_img.write(f.read())
            tmp_img.flush()

        results = []
        modes = ["simple", "advanced"]
        stego_images = []

        for mode in modes:
            key = generate_aes_key()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
                 tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls:
                
                # Encode
                start = time.time()
                encode_lsb(tmp_img.name, message, tmp_stego.name, tmp_pls.name if mode=="simple" else None, key, mode=mode)
                enc_time = time.time() - start
                
                # Decode
                start = time.time()
                decoded = decode_lsb(tmp_stego.name, tmp_pls.name if mode=="simple" else None, key)
                dec_time = time.time() - start
                
                # Metrics
                orig = np.array(Image.open(tmp_img.name).convert("RGB"), dtype=np.float64)
                stego = np.array(Image.open(tmp_stego.name).convert("RGB"), dtype=np.float64)
                mse = np.mean((orig - stego)**2)
                psnr = float("inf") if mse==0 else 20*np.log10(255.0/np.sqrt(mse))
                
                stego_images.append(tmp_stego.name)
                
                results.append({
                    "mode": mode.upper(),
                    "mse": f"{mse:.6f}",
                    "psnr": f"{psnr:.2f} dB",
                    "encode_time": f"{enc_time:.3f}s",
                    "decode_time": f"{dec_time:.3f}s",
                    "decoded": decoded[:100]+"..." if len(decoded)>100 else decoded
                })
        
        # Markdown table
        table = "\n\n### 📊 Bảng So Sánh Chi Tiết\n\n"
        table += "| Chế độ | MSE | PSNR | Thời gian mã hóa | Thời gian giải mã | Tin nhắn preview |\n"
        table += "|--------|-----|------|-----------------|-----------------|-----------------|\n"
        for res in results:
            table += f"| {res['mode']} | {res['mse']} | {res['psnr']} | {res['encode_time']} | {res['decode_time']} | {res['decoded']} |\n"
        
        gr.Info("✅ So sánh hoàn tất!")
        return stego_images, table

    except Exception as e:
        gr.Error(f"❌ Lỗi khi chạy so sánh: {str(e)}")
        return None, "Đã xảy ra lỗi"

# ===== Interface =====
def create_interface():
    with gr.Blocks(title="AES LSB Steganography", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🔐 Giấu Tin Mật Trong Ảnh Với AES")
        gr.Markdown("**LSB + PLS + AES**: giấu tin nhắn bảo mật trong ảnh.")

        with gr.Tabs():
            # --- Quick Encode ---
            with gr.Tab("🚀 Kiểm Tra Nhanh"):
                gr.Markdown("### Tải ảnh lên và mã hóa tin nhắn")
                with gr.Row():
                    with gr.Column():
                        quick_image = gr.Image(label="📷 Ảnh Gốc", type="filepath", height=400)
                        quick_message = gr.Textbox(label="💬 Tin Nhắn", lines=5)
                        quick_mode = gr.Dropdown(choices=["simple","advanced"], label="🔧 Mode Selection", value="simple")
                        quick_btn = gr.Button("🚀 Mã Hóa", variant="primary", size="lg")
                    with gr.Column():
                        quick_stego = gr.Image(label="🖼️ Ảnh Stego", type="filepath", height=400)
                        quick_pls = gr.File(label="📥 File PLS (.enc) - Chỉ Simple", interactive=False)
                        quick_key = gr.File(label="📥 File Khóa AES", interactive=False)
                        quick_decoded = gr.Textbox(label="📖 Tin Nhắn Đã Giải Mã", interactive=False, lines=8)
                with gr.Row():
                    quick_time = gr.Textbox(label="⏱️ Thời Gian", interactive=False, lines=1)
                with gr.Row():
                    quick_plot = gr.Image(label="📊 Histogram", type="filepath", height=300)

                def toggle_quick_pls(mode):
                    return gr.update(visible=(mode=="simple"))
                quick_mode.change(toggle_quick_pls, quick_mode, quick_pls)

                quick_btn.click(
                    fn=auto_encode_decode,
                    inputs=[quick_image, quick_message, quick_mode],
                    outputs=[quick_stego, quick_pls, quick_key, quick_decoded, quick_time, quick_plot, quick_time, quick_time]
                )

            # --- Decode ---
            with gr.Tab("🔓 Giải Mã Tin Nhắn"):
                gr.Markdown("### Tải ảnh stego và giải mã tin nhắn")
                with gr.Row():
                    with gr.Column():
                        decode_mode = gr.Dropdown(choices=["simple","advanced"], label="🔧 Mode Selection", value="simple")
                        decode_pls = gr.File(label="📁 File PLS (.enc) - Chỉ Simple", file_types=[".enc"])
                        decode_key = gr.File(label="🔑 File Khóa AES (.txt)", file_types=[".txt"])
                    with gr.Column():
                        decode_stego = gr.Image(label="📁 Ảnh Stego", type="filepath", height=400)
                decode_btn = gr.Button("🔓 Giải Mã", variant="primary", size="lg")
                decode_output = gr.Textbox(label="📝 Tin Nhắn Đã Giải Mã", interactive=False, lines=8)

                def toggle_decode_pls(mode):
                    return gr.update(visible=(mode=="simple"))
                decode_mode.change(toggle_decode_pls, decode_mode, decode_pls)

                decode_btn.click(fn=decode_message,
                                 inputs=[decode_stego, decode_pls, decode_key, decode_mode],
                                 outputs=[decode_output])

            # --- So sánh ---
            with gr.Tab("🧪 So Sánh Các Chế Độ"):
                gr.Markdown("### Kiểm tra cả 2 mode cùng lúc")
                with gr.Row():
                    with gr.Column():
                        test_image = gr.Image(label="📷 Ảnh Kiểm Tra", type="filepath", height=400)
                        test_message = gr.Textbox(label="💬 Tin Nhắn Kiểm Tra", lines=5)
                        test_btn = gr.Button("🧪 Chạy So Sánh", variant="primary", size="lg")
                    with gr.Column():
                        test_gallery = gr.Gallery(label="Ảnh Stego [Simple, Advanced]", columns=2, height=300)
                        test_output = gr.Markdown(label="📊 Kết Quả")

                test_btn.click(fn=lambda img,msg: run_tests(img,msg),
                               inputs=[test_image,test_message],
                               outputs=[test_gallery,test_output])
    return app

if __name__=="__main__":
    app=create_interface()
    app.launch(share=True, debug=True)
