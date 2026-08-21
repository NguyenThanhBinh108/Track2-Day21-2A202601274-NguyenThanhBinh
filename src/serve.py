"""
REST API suy luan, chay tren EC2 duoi quyen systemd service `income-api`.

Khi khoi dong, service tai model.joblib moi nhat tu S3
(artifacts/current/model.joblib) roi phuc vu du doan qua POST /score.

Xac thuc: EC2 instance profile (IAM role gan vao instance). boto3 tu tim
credentials theo thu tu chuan nen khong can file key nao tren dia.
"""

import os

import boto3
import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Income Model Inference Server")

ARTIFACT_BUCKET = os.environ["ARTIFACT_BUCKET"]
MODEL_KEY = "artifacts/current/model.joblib"
MODEL_PATH = os.path.expanduser("~/models/model.joblib")

# Nhan tra ve cho tung gia tri du doan cua mo hinh.
LABELS = {0: "thu_nhap_thap", 1: "thu_nhap_cao"}

# Thu tu 10 dac trung, khop voi FEATURE_COLUMNS trong prepare_data.py:
#   age, workclass, education_num, marital_status, occupation,
#   relationship, sex, capital_gain, capital_loss, hours_per_week
N_FEATURES = 10


def download_model():
    """
    Tai file model.joblib tu S3 ve may khi server khoi dong.

    Ham nay duoc goi mot lan khi module duoc import.
    """
    # 1. Client S3, xac thuc bang IAM role cua instance
    s3 = boto3.client("s3")

    # 2. Bao dam thu muc dich ton tai
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # 3. Tai file model xuong may
    s3.download_file(ARTIFACT_BUCKET, MODEL_KEY, MODEL_PATH)

    # 4. Thong bao thanh cong (xem bang: journalctl -u income-api)
    print(
        f"Model da duoc tai xuong tu s3://{ARTIFACT_BUCKET}/{MODEL_KEY} "
        f"-> {MODEL_PATH}"
    )


download_model()
model = joblib.load(MODEL_PATH)


class ScoreRequest(BaseModel):
    features: list[float]


@app.get("/healthz")
def healthz():
    """
    Endpoint kiem tra suc khoe server.
    GitHub Actions goi endpoint nay sau khi deploy de xac nhan server dang chay.

    Tra ve: {"status": "ok"}
    """
    # 5. Server da khoi dong va model da load xong neu request den duoc day
    return {"status": "ok"}


@app.post("/score")
def score(req: ScoreRequest):
    """
    Endpoint suy luan chinh.

    Dau vao : JSON {"features": [f1, f2, ..., f10]}
    Dau ra  : JSON {"prediction": <0|1>, "label": <"thu_nhap_thap"|"thu_nhap_cao">}

    Thu tu 10 dac trung (khop voi thu tu trong FEATURE_NAMES cua test):
        age, workclass, education_num, marital_status, occupation,
        relationship, sex, capital_gain, capital_loss, hours_per_week
    """
    # 6. Kiem tra so luong dac trung truoc khi goi model
    if len(req.features) != N_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="Expected 10 features (adult income)",
        )

    # 7. Du doan
    pred = int(model.predict([req.features])[0])

    # 8. Tra ve nhan cung voi gia tri du doan
    return {"prediction": pred, "label": LABELS[pred]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
