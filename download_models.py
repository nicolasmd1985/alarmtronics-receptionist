#!/usr/bin/env python3
"""
download_models.py - Model Downloader for Piper TTS & Faster-Whisper
Downloads neural voice models for Spanish and English voice synthesis.
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

VOICE_MODELS = {
    "es_ES": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json",
        "name": "es_ES-davefx-medium",
    },
    "en_US": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "name": "en_US-lessac-medium",
    },
}

def download_file(url: str, dest_path: Path):
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"[EXISTS] {dest_path.name} ({dest_path.stat().st_size // 1024} KB)")
        return

    print(f"[DOWNLOADING] {dest_path.name} from {url}...")
    try:
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, int(block_num * block_size * 100 / total_size))
                downloaded_mb = (block_num * block_size) / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                sys.stdout.write(f"\r  -> Progress: {percent}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)
        print(f"\n[OK] Saved {dest_path.name}")
    except Exception as e:
        print(f"\n[ERROR] Failed to download {url}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise

def main():
    print("==================================================")
    print("Piper TTS Model Asset Provisioner")
    print("Target Directory:", MODELS_DIR.resolve())
    print("==================================================")

    for lang, info in VOICE_MODELS.items():
        print(f"\n--- Checking Voice: {info['name']} ({lang}) ---")
        onnx_file = MODELS_DIR / f"{info['name']}.onnx"
        json_file = MODELS_DIR / f"{info['name']}.onnx.json"
        
        download_file(info["json"], json_file)
        download_file(info["onnx"], onnx_file)

    print("\nAll Piper TTS assets are verified and ready for real-time inference.")

if __name__ == "__main__":
    main()
