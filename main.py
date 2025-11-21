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

# ===== Calculate Max Message Size =====
def calculate_max_message(image_file, mode):
    if not image_file:
        return "Vui lòng tải ảnh để xem giới hạn"
    
    try:
        with Image.open(image_file) as im:
            width, height = im.size
            total_pixels = width * height
            
            # Tính overhead cho AES (IV + padding)
            aes_overhead = 16 + 16  # IV (16 bytes) + max padding (16 bytes)
            
            if mode == "advanced":
                # Advanced mode: cần trừ metadata header
                # Metadata format: "advanced:XXXX" (khoảng 20 bytes)
                # + AES overhead cho metadata
                metadata_size = 20 + aes_overhead
                metadata_bits = 16 + metadata_size * 8  # LENGTH_BITS + encrypted metadata
                header_pixels = (metadata_bits + 2) // 3
                
                available_pixels = total_pixels - header_pixels
                max_bits = available_pixels * 3
            else:
                # Simple mode: dùng toàn bộ ảnh
                max_bits = total_pixels * 3
            
            # Trừ overhead của AES
            max_bytes = (max_bits // 8) - aes_overhead
            max_kb = max_bytes / 1024
            max_chars = max_bytes  # Ước lượng (1 byte = 1 char cho ASCII)
            
            return f"📊 {width}x{height} | Tối đa: ~{max_chars:,} ký tự (~{max_kb:.1f} KB)"
    
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

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
        ax.plot(x, simple_hist, label="Simple (Random PLS)", color="green", linestyle="--", linewidth=1.5)
        ax.plot(x, advanced_hist, label="Advanced (Seeded PLS + Metadata)", color="red", linestyle=":", linewidth=1.5)
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
                        max_msg_info = gr.Textbox(label="📏 Kích thước tin nhắn tối đa", interactive=False, value="Vui lòng tải ảnh để xem giới hạn")
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
                
                # Update max message size when image or mode changes
                def update_max_info(img, mode):
                    return calculate_max_message(img, mode)
                
                image_input.change(update_max_info, [image_input, mode_dropdown], max_msg_info)
                mode_dropdown.change(update_max_info, [image_input, mode_dropdown], max_msg_info)

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
                
                #### **Simple Mode (LSB + Random PLS)**
                - PLS được sinh **hoàn toàn ngẫu nhiên**
                - PLS được mã hóa AES và lưu thành file `.enc` riêng
                - **Cần cả 3 file để giải mã**: Ảnh stego + File PLS + Khóa AES
                - Bảo mật cao nhờ thứ tự pixel không thể đoán trước
                - Phù hợp khi có kênh truyền an toàn cho file PLS
                
                #### **Advanced Mode (LSB + Seeded PLS + Metadata)**
                - PLS được sinh **deterministic** từ SHA256(key)
                - Metadata (độ dài message) được mã hóa và nhúng vào **header của ảnh** (16 bits đầu)
                - **Chỉ cần 2 file để giải mã**: Ảnh stego + Khóa AES (không cần file PLS)
                - Tự động tái tạo PLS từ khóa khi giải mã
                - Tiện lợi hơn khi truyền/lưu trữ (chỉ cần 2 file thay vì 3)
                - An toàn vì chỉ người có đúng khóa mới tái tạo được PLS
                
                #### **Mã hóa AES**
                - Tin nhắn được mã hóa AES-256 trước khi giấu vào ảnh
                - Khóa 256-bit được sinh ngẫu nhiên
                - Bảo vệ nội dung message ngay cả khi kẻ tấn công biết thuật toán
                
                ### 📊 Đánh Giá Chất Lượng
                - **MSE (Mean Squared Error)**: Đo sai khác trung bình giữa ảnh gốc và stego
                - **PSNR (Peak Signal-to-Noise Ratio)**: Đánh giá chất lượng ảnh (>40 dB = xuất sắc)
                - **Histogram**: Phân tích phân bố pixel để phát hiện dấu vết steganography
                """)

            # --- Hướng dẫn ---
            with gr.Tab("📚 Hướng Dẫn Sử Dụng"):
                gr.Markdown("""
                ## 📝 Mã Hóa
                1. Chọn tab **Mã Hóa Tin Nhắn**
                2. Chọn phương pháp:
                   - **Simple**: Cần lưu file PLS
                   - **Advanced**: Không cần file PLS
                3. Tải ảnh gốc (PNG khuyến nghị)
                4. Nhập tin nhắn bí mật
                5. Nhấn 🚀 **Mã Hóa**
                6. Tải về:
                   - Ảnh Stego (bắt buộc)
                   - Khóa AES (bắt buộc)
                   - File PLS (chỉ khi dùng Simple mode)

                ## 🔓 Giải Mã
                1. Chọn tab **Giải Mã Tin Nhắn**
                2. Chọn phương pháp tương ứng với lúc mã hóa
                3. Tải file:
                   - **Simple**: Ảnh stego + File PLS + Khóa AES
                   - **Advanced**: Ảnh stego + Khóa AES (không cần PLS)
                4. Nhấn 🔓 **Giải Mã**
                5. Xem tin nhắn đã giải mã

                ## 🧪 So Sánh
                1. Chọn tab **So Sánh Phương Pháp**
                2. Tải ảnh thử nghiệm
                3. Nhập tin nhắn test
                4. Nhấn 🧪 **So Sánh**
                5. Xem kết quả:
                   - Ảnh stego của cả 2 phương pháp
                   - Bảng so sánh MSE/PSNR/thời gian
                   - Biểu đồ histogram overlay

                ## 🔑 Lưu Ý Quan Trọng
                ⚠️ **Bảo mật:**
                - **KHÔNG BAO GIỜ** chia sẻ khóa AES qua kênh không an toàn
                - File PLS (Simple mode) cũng cần bảo mật như khóa AES
                - Mất khóa = mất tin nhắn vĩnh viễn
                
                ⚠️ **Format ảnh:**
                - Dùng **PNG** để tránh mất dữ liệu do nén
                - **TRÁNH JPG** vì nén lossy sẽ phá hủy LSB
                - Ảnh gốc phải đủ lớn để chứa tin nhắn
                
                ⚠️ **Giới hạn:**
                - Tin nhắn tối đa phụ thuộc vào kích thước ảnh
                - Công thức: `max_chars ≈ (width × height × 3) / 8`
                - Ví dụ: Ảnh 512×512 → ~98KB tin nhắn
                """)
    return app

if __name__=="__main__":
    app = create_interface()
    app.launch(share=True, debug=True)