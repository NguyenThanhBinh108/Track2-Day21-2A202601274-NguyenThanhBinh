import os

import mlflow
import pytest


@pytest.fixture(scope="session", autouse=True)
def isolate_mlflow_tracking(tmp_path_factory):
    """
    Chuyen MLflow sang thu muc tam trong suot phien chay test.

    Ba test trong file nay deu goi train() tren du lieu ngau nhien (f1 khoang 0.3).
    Neu khong tach ra, chung se lan vao mlflow.db thuc va lam ban anh chup MLflow UI
    o Buoc 1, vi UI se hien ca cac lan chay khong phai thi nghiem that.
    """
    # Tro vao mot thu muc CHUA ton tai: MLflow chi tu tao experiment mac dinh
    # (ID 0) khi no phai khoi tao store tu dau. Neu tro vao thu muc da co san
    # nhung rong, MLflow bao "Could not find experiment with ID 0".
    tracking_uri = (tmp_path_factory.mktemp("mlflow") / "mlruns").as_uri()
    os.environ["MLFLOW_TRACKING_URI"] = tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    yield
