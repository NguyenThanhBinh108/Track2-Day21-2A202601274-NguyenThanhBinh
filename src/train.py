"""
Huan luyen mo hinh du doan thu nhap (Adult / Census Income) va ghi nhan vao MLflow.

Chi so quyet dinh cua lab nay la f1_score cua LOP DUONG (thu nhap > 50K),
KHONG phai accuracy. Ly do: bo du lieu Adult co ty le lop 75/25, nen mot mo hinh
doan bua "thu nhap thap" cho moi mau da dat accuracy 0.752 ma khong hoc duoc gi.
"""

import json
import os

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import (
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Nguong chat luong: chi mo hinh dat f1_score >= 0.65 moi duoc trien khai.
F1_THRESHOLD = 0.65

# Ty le lop duong tham chieu cua bo du lieu goc (24.8%), dung cho canh bao drift.
REFERENCE_POSITIVE_RATE = 0.248
DRIFT_TOLERANCE = 0.05  # lech qua 5 diem phan tram thi canh bao

# Khai bao san requirements cho mlflow.sklearn.log_model. Neu khong truyen,
# MLflow tu suy luan moi truong bang mot subprocess pip. Do tren may nay:
# 2.95 s khi de MLflow tu suy luan, 1.84 s khi khai bao tuong minh.
MODEL_PIP_REQUIREMENTS = [
    "scikit-learn==1.4.2",
    "pandas==2.2.2",
    "joblib==1.4.2",
]

REPORT_PATH = "outputs/report.json"
DETAIL_PATH = "outputs/detail.txt"
MODEL_PATH = "models/model.joblib"


def build_model(params: dict):
    """
    Tao mo hinh boosting tu dict sieu tham so.

    params co the chua khoa tuy chon "model":
        "gb"   (mac dinh) -> GradientBoostingClassifier: dung lop model ma huong
                             dan lab yeu cau, tim diem split chinh xac.
        "hist"            -> HistGradientBoostingClassifier: cung ho boosting,
                             nhung binning histogram + da luong nen nhanh hon
                             hang chuc lan tren cung sieu tham so.

    Tra ve: (model, model_type, sieu_tham_so_da_dung)
    """
    params = dict(params)
    model_type = str(params.pop("model", "gb")).lower()

    n_estimators = params.pop("n_estimators", 100)
    learning_rate = params.pop("learning_rate", 0.1)
    max_depth = params.pop("max_depth", 3)

    if model_type in ("hist", "hgb", "histgradientboosting"):
        model = HistGradientBoostingClassifier(
            max_iter=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=42,
            **params,
        )
        model_type = "hist"
    else:
        model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            random_state=42,
            **params,
        )
        model_type = "gb"

    used = {
        "model": model_type,
        "n_estimators": n_estimators,
        "learning_rate": learning_rate,
        "max_depth": max_depth,
    }
    return model, model_type, used


def check_drift(y_train) -> float:
    """
    [Bonus 5] Canh bao lech lac du lieu.

    Tinh ty le lop duong trong tap huan luyen va so voi ty le tham chieu 24.8%.
    Lech qua DRIFT_TOLERANCE thi in canh bao ro rang vao log pipeline.
    """
    rate = float(np.mean(y_train))
    delta = rate - REFERENCE_POSITIVE_RATE
    if abs(delta) > DRIFT_TOLERANCE:
        print(
            f"CANH BAO DRIFT: ty le lop duong = {rate:.3f}, "
            f"lech {delta:+.3f} so voi tham chieu {REFERENCE_POSITIVE_RATE:.3f}."
        )
    else:
        print(
            f"Kiem tra phan phoi: ty le lop duong = {rate:.3f} "
            f"({delta:+.3f} so voi tham chieu) - trong nguong cho phep."
        )
    return rate


def scan_threshold(y_true, proba) -> tuple:
    """
    [Bonus 2] Quet nguong quyet dinh tu 0.10 den 0.90 (buoc 0.05).

    model.predict() mac dinh cat tai 0.5, hiem khi la nguong toi uu voi du lieu
    mat can bang. Tra ve (nguong tot nhat, f1 tai nguong do).
    """
    best_threshold, best_f1 = 0.5, -1.0
    for threshold in np.arange(0.10, 0.905, 0.05):
        f1 = f1_score(y_true, (proba >= threshold).astype(int), zero_division=0)
        if f1 > best_f1:
            best_threshold, best_f1 = float(threshold), float(f1)
    return round(best_threshold, 2), best_f1


def write_detail_report(y_true, preds) -> None:
    """
    [Bonus 3] Ghi confusion matrix va precision/recall tung lop ra outputs/detail.txt.
    """
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    (tn, fp), (fn, tp) = cm

    lines = [
        "BAO CAO CHI TIET - PHAN LOAI THU NHAP",
        "",
        "Confusion matrix (hang = thuc te, cot = du doan):",
        "                 pred:thap   pred:cao",
        f"  thuc:thap      {tn:9d}   {fp:8d}",
        f"  thuc:cao       {fn:9d}   {tp:8d}",
        "",
        "Chi so tung lop:",
    ]
    for label, name in ((0, "thu_nhap_thap"), (1, "thu_nhap_cao")):
        precision = precision_score(y_true, preds, pos_label=label, zero_division=0)
        recall = recall_score(y_true, preds, pos_label=label, zero_division=0)
        f1 = f1_score(y_true, preds, pos_label=label, zero_division=0)
        lines.append(
            f"  {name:<14} precision={precision:.4f}  recall={recall:.4f}  f1={f1:.4f}"
        )
    lines += [
        "",
        f"Bo sot nguoi thu nhap cao (false negative): {fn}",
        f"Gan nham nguoi thu nhap thap (false positive): {fp}",
        "",
    ]

    os.makedirs("outputs", exist_ok=True)
    with open(DETAIL_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


def train(
    params: dict,
    data_path: str = "data/train_batch1.csv",
    eval_path: str = "data/holdout.csv",
) -> float:
    """
    Huan luyen mo hinh va ghi nhan ket qua vao MLflow.

    Tham so:
        params     : dict chua cac sieu tham so cho mo hinh boosting.
        data_path  : duong dan den file du lieu huan luyen.
        eval_path  : duong dan den file du lieu danh gia (holdout).

    Tra ve:
        f1 (float): diem F1 cua lop duong (thu nhap > 50K) tren tap holdout.
    """

    # 1. Doc du lieu huan luyen va danh gia
    df_train = pd.read_csv(data_path)
    df_eval = pd.read_csv(eval_path)

    # 2. Tach dac trung (X) va nhan (y)
    X_train = df_train.drop(columns=["target"])
    y_train = df_train["target"]
    X_eval = df_eval.drop(columns=["target"])
    y_eval = df_eval["target"]

    with mlflow.start_run():

        # 3. Ghi nhan cac sieu tham so
        model, model_type, used_params = build_model(params)
        mlflow.log_params(used_params)
        mlflow.log_param("n_train_rows", len(df_train))

        # [Bonus 5] Kiem tra phan phoi truoc khi huan luyen
        positive_rate = check_drift(y_train)
        mlflow.log_metric("train_positive_rate", positive_rate)

        # 4. Huan luyen
        model.fit(X_train, y_train)

        # 5. Du doan tren tap holdout va tinh chi so.
        #    f1_score o day tinh cho LOP DUONG (target = 1) - KHONG dung average,
        #    vi average="weighted"/"macro" bi lop da so keo len va lam mat y nghia
        #    cua nguong 0.65.
        preds = model.predict(X_eval)
        f1 = float(f1_score(y_eval, preds, zero_division=0))
        acc = float(accuracy_score(y_eval, preds))

        # [Bonus 2] Quet nguong quyet dinh thay vi chi dung mac dinh 0.5
        proba = model.predict_proba(X_eval)[:, 1]
        best_threshold, best_f1 = scan_threshold(y_eval, proba)

        # 6. Ghi nhan chi so vao MLflow
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("best_threshold", best_threshold)
        mlflow.log_metric("f1_at_best_threshold", best_f1)
        mlflow.sklearn.log_model(
            model, "model", pip_requirements=MODEL_PIP_REQUIREMENTS
        )

        # 7. In ket qua ra man hinh
        print(f"F1: {f1:.4f} | Accuracy: {acc:.4f}")
        print(
            f"Nguong toi uu: {best_threshold:.2f} -> F1 = {best_f1:.4f} "
            f"(nguong mac dinh 0.50 -> F1 = {f1:.4f})"
        )

        # [Bonus 3] Bao cao precision/recall chi tiet
        write_detail_report(y_eval, preds)

        # 8. Luu metrics ra file outputs/report.json.
        #    File nay duoc doc boi GitHub Actions o Buoc 2.
        os.makedirs("outputs", exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "f1_score": f1,
                    "accuracy": acc,
                    "model": model_type,
                    "n_train_rows": len(df_train),
                    "train_positive_rate": positive_rate,
                    "best_threshold": best_threshold,
                    "f1_at_best_threshold": best_f1,
                },
                f,
                indent=2,
            )

        # 9. Luu mo hinh ra file models/model.joblib.
        #    File nay duoc upload len cloud storage o Buoc 2.
        os.makedirs("models", exist_ok=True)
        joblib.dump(model, MODEL_PATH)

    # 10. Tra ve f1 de cac ham goi train() doc duoc ket qua
    return f1


if __name__ == "__main__":
    with open("params.yaml") as f:
        params = yaml.safe_load(f)
    train(params)
