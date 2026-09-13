"""Download weights from HF into ~/.privatecopy/models/<id>/ (or ONNX dir).

- openmed-44m: snapshot from HF, then optimum ONNX export if torch present.
- nvidia-gliner: snapshot from HF (gliner lib reads safetensors directly);
  ONNX export attempted if `gliner` supports export_to_onnx.
Never commit weights (see .gitignore).
"""
from __future__ import annotations

import argparse
import os

from privatecopy.models.manifest import get_entry


def download_model(model_id: str, models_dir: str) -> str:
    entry = get_entry(model_id)
    dest = os.path.join(models_dir, model_id)
    os.makedirs(dest, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("pip install huggingface_hub  (needed for first download)")
        print(f"Manual: download https://huggingface.co/{entry['hf_repo']} into {dest}")
        return dest
    print(f"Downloading {entry['hf_repo']} -> {dest} ...")
    snapshot_download(repo_id=entry["hf_repo"], local_dir=dest,
                      local_dir_use_symlinks=False, resume_download=True)
    print("Download complete. Attempting ONNX export (optional, needs torch)...")
    try:
        from scripts.export_onnx import export_model
        export_model(model_id, dest)
    except Exception as e:
        print(f"ONNX export skipped ({e}). PyTorch/gliner runtime will still work.")
    with open(os.path.join(dest, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(f"Model: {entry['hf_repo']}\nLicense: {entry['license']}\n")
        if "NVIDIA" in entry["license"]:
            f.write("Licensed by NVIDIA Corporation under the NVIDIA Open Model License.\n")
    return dest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="nvidia-gliner", choices=["nvidia-gliner", "openmed-44m"])
    p.add_argument("--models-dir", default=os.path.join(os.path.expanduser("~"), ".privatecopy", "models"))
    a = p.parse_args()
    download_model(a.model, a.models_dir)
