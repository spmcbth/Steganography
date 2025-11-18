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

# ===== Encode & Decode =====
def auto_encode_decode(image_file, message, mode):
    if not image_file or not message:
        gr.Warning("⚠️ Vui lòng cung cấp ảnh và tin nhắn")
        return None, None, None, None, None, None, None
    
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

            # Encode
            start_enc = time.time()
            encode_lsb(tmp_img.name, message, tmp_stego.name, tmp_pls.name if mode=="simple" else None, key, mode=mode)
            enc_time = time.time() - start_enc
            
            # Metrics
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
            ax.set_title(f"So sánh Histogram - Phương pháp: {mode.capitalize()}")
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

            metrics_text = f"MSE: {mse:.6f} | PSNR: {psnr:.2f} dB"
            time_text = f"⏱️ Thời gian mã hóa: {enc_time:.3f}s"

            return (stego_path, pls_path, key_path,
                    time_text, temp_plot.name, metrics_text, metrics_text)

    except Exception as e:
        gr.Error(f"❌ Lỗi: {str(e)}")
        return None, None, None, None, None, None, None

# ===== Decode Message =====
def decode_message(stego_file, pls_file, key_file, mode):
    if not stego_file or not key_file:
        gr.Warning("⚠️ Cần ảnh stego và khóa AES")
        return None, None
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
            
            start_dec = time.time()
            decoded_message = decode_lsb(tmp_stego.name, pls_path, key)
            dec_time = time.time() - start_dec
            
            time_text = f"⏱️ Thời gian giải mã: {dec_time:.3f}s"
            
            return decoded_message, time_text
    except Exception as e:
        gr.Error(f"❌ Lỗi khi giải mã: {str(e)}")
        return None, None

# ===== Run Tests cho 2 phương pháp =====
def run_tests(image_file, message):
    if not image_file or not message:
        gr.Warning("⚠️ Vui lòng cung cấp ảnh và tin nhắn")
        return None, "Không có kết quả", None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
            with open(image_file, "rb") as f:
                tmp_img.write(f.read())
            tmp_img.flush()

        results = []
        methods = ["simple", "advanced"]
        stego_images = []

        for method in methods:
            key = generate_aes_key()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_stego, \
                 tempfile.NamedTemporaryFile(delete=False, suffix=".enc") as tmp_pls:
                
                # Resolution
                with Image.open(tmp_img.name) as im:
                    width, height = im.size
                
                # Encode
                start = time.time()
                encode_lsb(tmp_img.name, message, tmp_stego.name, tmp_pls.name if method=="simple" else None, key, mode=method)
                enc_time = time.time() - start
                
                # Decode
                start = time.time()
                decoded = decode_lsb(tmp_stego.name, tmp_pls.name if method=="simple" else None, key)
                dec_time = time.time() - start
                
                # Metrics
                orig = np.array(Image.open(tmp_img.name).convert("RGB"), dtype=np.float64)
                stego = np.array(Image.open(tmp_stego.name).convert("RGB"), dtype=np.float64)
                mse = np.mean((orig - stego)**2)
                psnr = float("inf") if mse==0 else 20*np.log10(255.0/np.sqrt(mse))
                
                stego_images.append(tmp_stego.name)
                
                results.append({
                    "method": method.capitalize(),
                    "resolution": f"{width}x{height}",
                    "mse": f"{mse:.6f}",
                    "psnr": f"{psnr:.2f} dB",
                    "encode_time": f"{enc_time:.3f}s",
                    "decode_time": f"{dec_time:.3f}s",
                    "decoded": decoded[:100]+"..." if len(decoded)>100 else decoded
                })
        
        # Markdown table
        table = "\n\n### 📊 Bảng So Sánh Chi Tiết\n\n"
        table += "| Phương pháp | Resolution | MSE | PSNR | Thời gian mã hóa | Thời gian giải mã | Tin nhắn |\n"
        table += "|-------------|------------|-----|------|------------------|-------------------|----------|\n"
        for res in results:
            table += f"| {res['method']} | {res['resolution']} | {res['mse']} | {res['psnr']} | {res['encode_time']} | {res['decode_time']} | {res['decoded']} |\n"
        
        # Histogram comparison
        orig_gray = np.array(Image.open(tmp_img.name).convert("L"))
        simple_gray = np.array(Image.open(stego_images[0]).convert("L"))
        advanced_gray = np.array(Image.open(stego_images[1]).convert("L"))
        
        orig_hist, _ = np.histogram(orig_gray.flatten(), bins=256, range=(0,255))
        simple_hist, _ = np.histogram(simple_gray.flatten(), bins=256, range=(0,255))
        advanced_hist, _ = np.histogram(advanced_gray.flatten(), bins=256, range=(0,255))
        
        x = np.arange(256)
        fig, ax = plt.subplots(figsize=(12,5))
        ax.plot(x, orig_hist, label="Ảnh gốc", color="blue", linewidth=2)
        ax.plot(x, simple_hist, label="Simple (LSB + PLS)", color="green", linestyle="--", linewidth=1.5)
        ax.plot(x, advanced_hist, label="Advanced (LSB thuần)", color="red", linestyle=":", linewidth=1.5)
        ax.set_title("So sánh Histogram - Cả 2 Phương Pháp")
        ax.set_xlabel("Giá trị Pixel")
        ax.set_ylabel("Số lượng")
        ax.set_xlim(0,255)
        ax.legend()
        temp_plot = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(temp_plot.name, dpi=150, bbox_inches="tight")
        plt.close()
        
        gr.Info("✅ So sánh hoàn tất!")
        return stego_images, table, temp_plot.name

    except Exception as e:
        gr.Error(f"❌ Lỗi khi chạy so sánh: {str(e)}")
        return None, "Đã xảy ra lỗi", None

# ===== Giao diện Gradio =====
def create_interface():
    with gr.Blocks(title="Steganography LSB + AES", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🔐 Hệ thống Giấu Tin Trong Ảnh")
        gr.Markdown("Hệ thống **Steganography LSB** kết hợp **AES encryption** và **Pixel Location Sequence (PLS)** để giấu tin nhắn bí mật trong ảnh.")

        with gr.Tabs():
            # --- Mã Hóa ---
            with gr.Tab("🔒 Mã Hóa Tin Nhắn"):
                gr.Markdown("### Tải ảnh và mã hóa tin nhắn bí mật")
                with gr.Row():
                    mode_dropdown = gr.Dropdown(choices=["simple","advanced"], label="🔧 Phương Pháp Giấu Tin", value="simple")
                with gr.Row():
                    with gr.Column():
                        image_input = gr.Image(label="📷 Ảnh Gốc", type="filepath", height=430)
                    with gr.Column():
                        message_input = gr.Textbox(label="💬 Tin Nhắn Cần Giấu", lines=5, placeholder="Nhập tin nhắn bí mật...")
                with gr.Row():
                    encode_btn = gr.Button("🚀 Mã Hóa", variant="primary", size="lg")
                with gr.Row():
                    with gr.Column():
                        stego_output = gr.Image(label="🖼️ Ảnh Stego", type="filepath", height=400)
                    with gr.Column():
                        pls_output = gr.File(label="📥 File PLS (.enc)", interactive=False)
                        key_output = gr.File(label="🔑 File Khóa AES", interactive=False)
                with gr.Row():
                    encode_time = gr.Textbox(label="⏱️ Thời Gian Mã Hóa", interactive=False)
                with gr.Row():
                    metrics_output = gr.Textbox(label="📈 Chất Lượng Ảnh", interactive=False)
                with gr.Row():
                    hist_output = gr.Image(label="📊 Biểu Đồ Histogram", type="filepath", height=300)

                def toggle_pls(mode):
                    return gr.update(visible=(mode=="simple"))
                mode_dropdown.change(toggle_pls, mode_dropdown, pls_output)

                encode_btn.click(
                    fn=auto_encode_decode,
                    inputs=[image_input, message_input, mode_dropdown],
                    outputs=[stego_output, pls_output, key_output, encode_time, hist_output, metrics_output, metrics_output]
                )

            # --- Giải Mã ---
            with gr.Tab("🔓 Giải Mã Tin Nhắn"):
                gr.Markdown("### Giải mã tin nhắn từ ảnh Stego")
                with gr.Row():
                    decode_mode = gr.Dropdown(choices=["simple","advanced"], label="🔧 Phương Pháp Giải Mã", value="simple")
                with gr.Row():
                    with gr.Column():
                        decode_image = gr.Image(label="📁 Ảnh Stego", type="filepath", height=430)
                    with gr.Column():
                        decode_pls_file = gr.File(label="📁 File PLS (.enc)", file_types=[".enc"])
                        decode_key_file = gr.File(label="🔑 File Khóa AES (.txt)", file_types=[".txt"])
                with gr.Row():
                    decode_btn = gr.Button("🔓 Giải Mã", variant="primary", size="lg")
                with gr.Row():
                    decoded_message_output = gr.Textbox(label="📝 Tin Nhắn Giải Mã", interactive=False, lines=15)
                    decode_time_output = gr.Textbox(label="⏱️ Thời Gian Giải Mã", interactive=False)

                def toggle_decode_pls(mode):
                    return gr.update(visible=(mode=="simple"))
                decode_mode.change(toggle_decode_pls, decode_mode, decode_pls_file)

                decode_btn.click(
                    fn=decode_message,
                    inputs=[decode_image, decode_pls_file, decode_key_file, decode_mode],
                    outputs=[decoded_message_output, decode_time_output]
                )

            # --- So Sánh ---
            with gr.Tab("🧪 So Sánh Phương Pháp"):
                gr.Markdown("### Kiểm tra và so sánh hiệu suất giữa 2 phương pháp")
                with gr.Row():
                    test_image_input = gr.Image(label="📷 Ảnh Kiểm Tra", type="filepath", height=350)
                    test_message_input = gr.Textbox(label="💬 Tin Nhắn Kiểm Tra", lines=10, placeholder="Nhập tin nhắn để thử nghiệm...")
                with gr.Row():
                    test_btn = gr.Button("🧪 So Sánh", variant="primary", size="lg")
                with gr.Row():
                    test_gallery = gr.Gallery(label="🖼️ Ảnh Stego [Simple, Advanced]", columns=2, height=350)
                with gr.Row():
                    test_table = gr.Markdown(label="📊 Kết Quả So Sánh")
                with gr.Row():
                    test_histogram = gr.Image(label="📊 Biểu Đồ Histogram", type="filepath", height=350)

                test_btn.click(
                    fn=run_tests,
                    inputs=[test_image_input, test_message_input],
                    outputs=[test_gallery, test_table, test_histogram]
                )

            # --- Giới thiệu ---
            with gr.Tab("ℹ️ Giới Thiệu"):
                gr.Markdown("""
                ## 📖 Giới Thiệu Hệ Thống
                Hệ thống **Steganography LSB** kết hợp **AES encryption** và **Pixel Location Sequence (PLS)** để giấu tin nhắn bí mật.
                
                ### 🎯 Mục Đích
                - Bảo mật thông tin nhạy cảm
                - So sánh hiệu quả giữa 2 phương pháp: Simple & Advanced
                - Đánh giá chất lượng ảnh qua MSE/PSNR và histogram
                
                ### 🔧 Tính Năng Chính
                **Simple (LSB + PLS)**: Cần file PLS để giải mã, bảo mật cao nhờ thứ tự pixel ngẫu nhiên  
                **Advanced (LSB thuần)**: Không cần file PLS, giải mã đơn giản  
                **Mã hóa AES**: Tin nhắn được mã hóa trước khi giấu, khóa 256-bit
                """)

            # --- Hướng dẫn ---
            with gr.Tab("📚 Hướng Dẫn Sử Dụng"):
                gr.Markdown("""
                ## 📝 Mã Hóa
                1. Chọn tab Mã Hóa Tin Nhắn  
                2. Chọn phương pháp mã hóa (Simple/Advanced)  
                3. Tải ảnh gốc (PNG)  
                4. Nhập tin nhắn  
                5. Nhấn 🚀 Mã Hóa  
                6. Tải ảnh Stego, khóa AES, file PLS (nếu có)

                ## 🔓 Giải Mã
                1. Chọn tab Giải Mã Tin Nhắn  
                2. Chọn phương pháp giải mã (Simple/Advanced)  
                3. Tải ảnh Stego, khóa AES, file PLS (nếu có)  
                4. Nhấn 🔓 Giải Mã

                ## 🧪 So Sánh
                1. Chọn tab So Sánh  
                2. Tải ảnh và nhập tin nhắn thử nghiệm  
                3. Nhấn 🧪 So Sánh  
                4. Xem ảnh stego, bảng MSE/PSNR, thời gian, histogram

                ## 🔑 Lưu ý
                - Không chia sẻ khóa AES  
                - Dùng ảnh PNG, tránh dùng JPG để giảm thiểu mất dữ liệu
                """)
    return app

if __name__=="__main__":
    app = create_interface()
    app.launch(share=True, debug=True)