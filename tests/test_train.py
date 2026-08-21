import json
import os

import numpy as np
import pandas as pd

from src.train import train

FEATURE_NAMES = [
    "age", "workclass", "education_num", "marital_status", "occupation",
    "relationship", "sex", "capital_gain", "capital_loss", "hours_per_week",
]

# Sieu tham so nho, chi de kiem tra luong chay cua ham train() - khong nham
# muc dich dat chat luong mo hinh.
SMOKE_PARAMS = {"n_estimators": 10, "learning_rate": 0.1, "max_depth": 2}


def _make_temp_data(tmp_path):
    """
    Tao dataset nho voi cung schema Adult de su dung trong test.

    pytest cung cap `tmp_path` la mot thu muc tam thoi, tu dong xoa sau khi test ket thuc.
    Ham nay dung du lieu ngau nhien nen khong can ket noi cloud storage hay tai file CSV thuc.
    """
    rng = np.random.default_rng(0)
    n = 200

    # 1. Mang dac trung (n, 10) voi gia tri trong [0, 1)
    X = rng.random((n, len(FEATURE_NAMES)))

    # 2. Nhan nhi phan. Bai toan nay chi co HAI lop (0 va 1), nen can tren la 2.
    y = rng.integers(0, 2, size=n)

    # 3. Ghep thanh DataFrame co cot "target"
    df = pd.DataFrame(X, columns=FEATURE_NAMES)
    df["target"] = y

    # 4. 160 dong dau lam tap huan luyen, 40 dong cuoi lam tap holdout
    train_path = str(tmp_path / "train.csv")
    eval_path = str(tmp_path / "holdout.csv")
    df.iloc[:160].to_csv(train_path, index=False)
    df.iloc[160:].to_csv(eval_path, index=False)

    # 5. Tra ve duong dan hai file vua tao
    return train_path, eval_path


def test_train_returns_float(tmp_path):
    """Kiem tra ham train() tra ve mot so thuc nam trong [0.0, 1.0]."""
    train_path, eval_path = _make_temp_data(tmp_path)

    # 6. Goi train() voi sieu tham so nho tren du lieu tam
    f1 = train(SMOKE_PARAMS, data_path=train_path, eval_path=eval_path)

    # 7. Kiem tra kieu va mien gia tri cua ket qua
    assert isinstance(f1, float)
    assert 0.0 <= f1 <= 1.0


def test_report_file_created(tmp_path):
    """Kiem tra file outputs/report.json duoc tao sau khi huan luyen."""
    train_path, eval_path = _make_temp_data(tmp_path)
    train(SMOKE_PARAMS, data_path=train_path, eval_path=eval_path)

    # 8. File ton tai va chua du hai chi so bat buoc
    assert os.path.exists("outputs/report.json")
    with open("outputs/report.json") as f:
        report = json.load(f)
    assert "f1_score" in report
    assert "accuracy" in report


def test_model_file_created(tmp_path):
    """Kiem tra file models/model.joblib duoc tao sau khi huan luyen."""
    train_path, eval_path = _make_temp_data(tmp_path)
    train(SMOKE_PARAMS, data_path=train_path, eval_path=eval_path)

    # 9. File model ton tai de buoc Release upload len cloud storage
    assert os.path.exists("models/model.joblib")
