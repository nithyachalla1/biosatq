from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def bits_to_bytes(key_bits, length_bytes=16):
    needed = length_bytes * 8
    if len(key_bits) < needed:
        raise ValueError("Not enough key bits")
    key_bytes = int(key_bits[:needed], 2).to_bytes(length_bytes, "big")
    return key_bytes

def aesgcm_encrypt_with_bits(key_bits, plaintext_bytes):
    key = bits_to_bytes(key_bits, 16)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext_bytes, None)
    return nonce + ct

def aesgcm_decrypt_with_bits(key_bits, ciphertext_bytes):
    key = bits_to_bytes(key_bits, 16)
    aesgcm = AESGCM(key)
    nonce = ciphertext_bytes[:12]
    ct = ciphertext_bytes[12:]
    pt = aesgcm.decrypt(nonce, ct, None)
    return pt
