"""Model catalog: ids, HF repos, licenses, labels, download locations."""
from __future__ import annotations

GLINER_LABELS = [
    "FIRST_NAME", "LAST_NAME", "DATE_OF_BIRTH", "AGE", "GENDER", "SSN",
    "PASSPORT_NUMBER", "DRIVER_LICENSE", "ACCOUNT_NUMBER", "CREDIT_DEBIT_CARD",
    "CVV", "BANK_ROUTING_NUMBER", "EMPLOYEE_ID", "MEDICAL_RECORD_NUMBER",
    "HEALTH_PLAN_BENEFICIARY_NUMBER", "CERTIFICATE_LICENSE_NUMBER", "API_KEY",
    "MAC_ADDRESS", "IPV4", "IPV6", "DEVICE_IDENTIFIER", "EMAIL", "PHONE_NUMBER",
    "FAX_NUMBER", "URL", "STREET_ADDRESS", "CITY", "COUNTY", "STATE", "COUNTRY",
    "COORDINATE", "ZIP_CODE", "COMPANY_NAME", "OCCUPATION", "EDUCATION_LEVEL",
    "BLOOD_TYPE", "BIOMETRIC_IDENTIFIER", "DATE", "DATE_TIME", "TIME",
    "USER_NAME", "PASSWORD",
]

MODEL_CATALOG: dict[str, dict] = {
    "nvidia-gliner": {
        "hf_repo": "nvidia/gliner-PII",
        "params": "570M (gliner_large-v2.1 based)",
        "runtime": "gliner + onnxruntime",
        "license": "NVIDIA Open Model License",
        "approx_size": "~1.1GB fp32 / ~350MB INT8 ONNX",
        "default_threshold": 0.5,
        "labels": GLINER_LABELS,
        "onnx_dir": "nvidia-gliner-onnx",
    },
    "openmed-44m": {
        "hf_repo": "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1",
        "params": "44M (deberta-v3-small)",
        "runtime": "optimum[onnx] + onnxruntime",
        "license": "Apache-2.0",
        "approx_size": "~170MB fp32 / ~45MB INT8 ONNX",
        "default_threshold": 0.5,
        "labels": ["* (54 token-classification types, see model card)"],
        "onnx_dir": "openmed-44m-onnx",
    },
}


def get_entry(model_id: str) -> dict:
    try:
        return MODEL_CATALOG[model_id]
    except KeyError:
        raise ValueError(f"unknown model {model_id!r}; choose from {sorted(MODEL_CATALOG)}") from None
