"""Build-time ONNX export. Run on a dev/CI machine with torch, not on user machines."""
from __future__ import annotations

import os


def export_model(model_id: str, model_dir: str) -> str | None:
    if model_id == "openmed-44m":
        from optimum.onnxruntime import ORTQuantizer
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
        from optimum.exporters.onnx import main_export
        onnx_dir = os.path.join(os.path.dirname(model_dir), "openmed-44m-onnx")
        main_export(model_id_or_path=model_dir, output=onnx_dir, task="token-classification", opset=14)
        quantizer = ORTQuantizer.from_pretrained(onnx_dir)
        quantizer.quantize(save_dir=onnx_dir, quantization_config=AutoQuantizationConfig.arm64()
                           if False else AutoQuantizationConfig.avx512_vnni())
        return onnx_dir
    if model_id == "nvidia-gliner":
        from gliner import GLiNER
        model = GLiNER.from_pretrained(model_dir)
        if hasattr(model, "export_to_onnx"):
            paths = model.export_to_onnx(save_dir=model_dir, onnx_filename="model.onnx", quantize=True)
            return str(paths)
        print("gliner build has no export_to_onnx; shipping PyTorch weights.")
        return None
    raise ValueError(model_id)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--dir", required=True)
    a = p.parse_args()
    print(export_model(a.model, a.dir))
