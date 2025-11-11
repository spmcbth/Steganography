from PIL import Image
import numpy as np
import random
import hashlib
from crypto_utils import aes_encrypt, aes_decrypt

METADATA_HEADER_PIXELS = 128

def generate_pls_seeded(total_pixels: int, needed_bits: int, key: bytes, offset: int = 0) -> list[int]:
    """PLS dựa trên key cho Advanced mode."""
    if needed_bits > (total_pixels - offset) * 3:
        raise ValueError("Not enough pixels for message.")
    seed = int(hashlib.sha256(key).hexdigest(), 16) % (2**32)
    random.seed(seed)
    arr = list(range(offset, total_pixels))
    for i in range(len(arr)-1, len(arr)-needed_bits//3-1, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[:needed_bits]

def generate_pls(total_pixels: int, needed_bits: int) -> list[int]:
    """Random PLS cho Simple mode."""
    if needed_bits > total_pixels * 3:
        raise ValueError("Not enough pixels for message.")
    arr = list(range(total_pixels))
    for i in range(len(arr)-1, len(arr)-needed_bits//3-1, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[:needed_bits]

def lsb_match(value, bit):
    bit = int(bit)
    if (value & 1) == bit:
        return value
    if value == 255: return 254
    if value == 0: return 1
    return value + random.choice([-1, 1])

def embed_metadata(im, metadata_bytes: bytes):
    bitstream = "".join(format(b,"08b") for b in metadata_bytes)
    if len(bitstream) > METADATA_HEADER_PIXELS*3:
        raise ValueError("Metadata too large")
    pixels = im.load()
    width, height = im.size
    idx = 0
    for px_idx in range(METADATA_HEADER_PIXELS):
        if idx >= len(bitstream): break
        row, col = divmod(px_idx, width)
        r,g,b = pixels[col,row]
        for ch in range(3):
            if idx>=len(bitstream): break
            bit = int(bitstream[idx])
            if ch==0: r=lsb_match(r, bit)
            elif ch==1: g=lsb_match(g, bit)
            else: b=lsb_match(b, bit)
            idx+=1
        pixels[col,row]=(r,g,b)

def extract_metadata(im, key: bytes, expected_length: int) -> bytes:
    pixels = im.load()
    width, height = im.size
    bitstream=""
    for px_idx in range(METADATA_HEADER_PIXELS):
        row, col = divmod(px_idx, width)
        r,g,b=pixels[col,row]
        bitstream+=str(r&1)+str(g&1)+str(b&1)
    encrypted_bytes=bytearray()
    for i in range(0, expected_length*8,8):
        byte_bits=bitstream[i:i+8]
        if len(byte_bits)<8: break
        encrypted_bytes.append(int(byte_bits,2))
    return aes_decrypt(bytes(encrypted_bytes), key)

def encode_lsb(image_path: str, message: str, stego_path: str, pls_enc_path: str, key: bytes, mode: str="simple"):
    im=Image.open(image_path)
    if im.mode!="RGB": im=im.convert("RGB")
    width,height=im.size
    total_pixels=width*height

    encrypted_msg = aes_encrypt(message.encode(), key)
    bitstream="".join(format(b,"08b") for b in encrypted_msg)
    needed_bits=len(bitstream)

    offset=0
    mode=mode.lower()
    if mode=="advanced":
        metadata=f"advanced:{len(encrypted_msg)}".encode()
        encrypted_metadata=aes_encrypt(metadata, key)
        embed_metadata(im, encrypted_metadata)
        offset=METADATA_HEADER_PIXELS
        pls=generate_pls_seeded(total_pixels, needed_bits, key, offset)
    elif mode=="simple":
        pls=generate_pls(total_pixels, needed_bits)
    else:
        raise ValueError("Invalid mode")

    pixels=im.load()
    for i, bit in enumerate(bitstream):
        x=pls[i]
        row,col=divmod(x,width)
        r,g,b=pixels[col,row]
        ch=i%3
        bval=int(bit)
        if ch==0: r=lsb_match(r,bval)
        elif ch==1: g=lsb_match(g,bval)
        else: b=lsb_match(b,bval)
        pixels[col,row]=(r,g,b)

    im.save(stego_path)

    if mode=="simple" and pls_enc_path:
        pls_bytes=",".join(map(str,pls)).encode()
        enc_pls=aes_encrypt(pls_bytes,key)
        with open(pls_enc_path,"wb") as f: f.write(enc_pls)

def decode_lsb(stego_path: str, pls_enc_path: str, key: bytes) -> str:
    im=Image.open(stego_path)
    if im.mode!="RGB": im=im.convert("RGB")
    width,height=im.size
    total_pixels=width*height

    if not pls_enc_path:
        metadata=extract_metadata(im,key,32)
        metadata_str=metadata.decode(errors="ignore")
        if metadata_str.startswith("advanced:"):
            n_bytes=int(metadata_str.split(":")[1])
            pls=generate_pls_seeded(total_pixels,n_bytes*8,key,METADATA_HEADER_PIXELS)
        else:
            raise ValueError("Invalid metadata")
    else:
        with open(pls_enc_path,"rb") as f: encrypted_data=f.read()
        decrypted_data=aes_decrypt(encrypted_data,key)
        pls=list(map(int,decrypted_data.decode().split(",")))

    pixels=im.load()
    bitstream=""
    for i,x in enumerate(pls):
        row,col=divmod(x,width)
        r,g,b=pixels[col,row]
        ch=i%3
        if ch==0: bitstream+=str(r&1)
        elif ch==1: bitstream+=str(g&1)
        else: bitstream+=str(b&1)

    encrypted_bytes=bytearray()
    for i in range(0,len(bitstream),8):
        byte_bits=bitstream[i:i+8]
        if len(byte_bits)<8: break
        encrypted_bytes.append(int(byte_bits,2))
    return aes_decrypt(bytes(encrypted_bytes), key).decode()
