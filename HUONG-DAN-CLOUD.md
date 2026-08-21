# Runbook AWS - Hạ Tầng Cho Bước 2 và Bước 3

Provider đã chọn: **AWS** (S3 cho object storage, EC2 cho serving).
Code đã được chuyển sang `dvc[s3]` + `boto3`.

Chạy trong **Git Bash**. `aws` nằm ngoài PATH mặc định của Git Bash nên mỗi terminal mới
cần thêm dòng export ở mục 0.

---

## 0. Biến môi trường (chạy lại mỗi terminal mới)

```bash
export PATH="$PATH:/c/Program Files/Amazon/AWSCLIV2"
export AWS_DEFAULT_REGION=ap-southeast-2          # Sydney - khớp region bạn đang dùng trên Console
export BUCKET=income-lab-2a202601274              # tên bucket phải unique toàn cầu
export SG=income-api-sg
export KEYNAME=income-deploy
```

---

## 1. Hai lệnh bạn phải tự chạy (không thể tự động hóa)

```bash
aws configure          # dán Access Key ID + Secret, region ap-southeast-2, output json
gh auth login          # chọn GitHub.com > HTTPS > Login with a web browser
```

`aws configure` cần một IAM user có quyền tạo S3 + EC2 + IAM. Nếu chưa có: đăng nhập AWS
Console > IAM > Users > Create user > đính kèm policy `AdministratorAccess` > tab Security
credentials > Create access key > chọn "Command Line Interface".

Kiểm tra:

```bash
aws sts get-caller-identity
gh auth status
```

- [ ] `aws sts get-caller-identity` trả về Account + Arn
- [ ] `gh auth status` báo đã đăng nhập

---

## 2. S3 bucket + IAM user cho CI

```bash
aws s3api create-bucket --bucket $BUCKET \
  --region $AWS_DEFAULT_REGION \
  --create-bucket-configuration LocationConstraint=$AWS_DEFAULT_REGION

aws iam create-user --user-name income-lab-user
```

Policy quyền tối thiểu — chỉ đọc/ghi/xóa object **trong đúng bucket này**, không cho xóa
bucket (tương đương `roles/storage.objectAdmin` mà lab yêu cầu):

```bash
aws iam put-user-policy --user-name income-lab-user \
  --policy-name income-lab-bucket-access \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {\"Effect\": \"Allow\", \"Action\": [\"s3:ListBucket\", \"s3:GetBucketLocation\"],
       \"Resource\": \"arn:aws:s3:::$BUCKET\"},
      {\"Effect\": \"Allow\", \"Action\": [\"s3:GetObject\", \"s3:PutObject\", \"s3:DeleteObject\"],
       \"Resource\": \"arn:aws:s3:::$BUCKET/*\"}
    ]
  }"

aws iam create-access-key --user-name income-lab-user > /tmp/ci-key.json
```

`/tmp/ci-key.json` là nguồn cho secret `STORAGE_CREDENTIALS`. **Không commit file này.**

- [ ] Bucket tạo xong, IAM user + access key tạo xong

---

## 3. DVC remote + push dữ liệu

`dvc init` và `dvc add` đã chạy sẵn; ba file `data/*.dvc` đã có trong repo.

```bash
dvc remote add -d labstore s3://$BUCKET/dvc
dvc remote modify labstore region $AWS_DEFAULT_REGION
dvc push
aws s3 ls s3://$BUCKET/dvc/ --recursive | head
```

DVC dùng credentials trong `~/.aws/credentials` (từ `aws configure`) nên không cần cấu hình
key riêng.

- [ ] `dvc push` thành công, `aws s3 ls` thấy file

---

## 4. IAM role cho EC2 đọc model từ S3

Dùng instance profile thay vì copy key lên máy: không có file bí mật nào nằm trên EC2, và
`boto3` tự nhận credentials mà không cần cấu hình gì trong `serve.py`.

```bash
aws iam create-role --role-name income-api-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
                   "Principal": {"Service": "ec2.amazonaws.com"},
                   "Action": "sts:AssumeRole"}]
  }'

aws iam put-role-policy --role-name income-api-role \
  --policy-name read-current-model \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{\"Effect\": \"Allow\", \"Action\": \"s3:GetObject\",
                     \"Resource\": \"arn:aws:s3:::$BUCKET/artifacts/*\"}]
  }"

aws iam create-instance-profile --instance-profile-name income-api-profile
aws iam add-role-to-instance-profile \
  --instance-profile-name income-api-profile --role-name income-api-role
```

- [ ] Role + instance profile tạo xong

---

## 5. Security group + key pair + EC2

```bash
aws ec2 create-security-group --group-name $SG \
  --description "Income API - SSH va inference port"
aws ec2 authorize-security-group-ingress --group-name $SG \
  --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name $SG \
  --protocol tcp --port 8080 --cidr 0.0.0.0/0

aws ec2 create-key-pair --key-name $KEYNAME \
  --query 'KeyMaterial' --output text > ~/.ssh/$KEYNAME.pem
chmod 400 ~/.ssh/$KEYNAME.pem
```

Key pair này dùng cho cả SSH thủ công và GitHub Actions - không cần tạo key thứ hai như
hướng dẫn GCP.

```bash
export AMI=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)

aws ec2 run-instances --image-id $AMI --instance-type t3.micro \
  --key-name $KEYNAME --security-groups $SG \
  --iam-instance-profile Name=income-api-profile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=income-api}]'

aws ec2 wait instance-running --filters "Name=tag:Name,Values=income-api"

export VM_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=income-api" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "VM_IP=$VM_IP"
```

`t3.micro` thuộc free tier. User SSH của Ubuntu AMI là **`ubuntu`**.

- [ ] EC2 đang chạy, ghi lại `VM_IP`

---

## 6. Cài môi trường trên EC2

**Quan trọng:** ghim `scikit-learn==1.4.2` giống [requirements.txt](requirements.txt). Model
được pickle bởi 1.4.2; bản khác sẽ làm `joblib.load` cảnh báo lệch phiên bản hoặc lỗi hẳn.

```bash
SSH="ssh -i ~/.ssh/$KEYNAME.pem -o StrictHostKeyChecking=no ubuntu@$VM_IP"

$SSH "sudo apt-get update -qq && sudo apt-get install -y python3-pip && \
  pip3 install --quiet 'scikit-learn==1.4.2' 'joblib==1.4.2' 'pandas==2.2.2' \
    'fastapi==0.111.0' 'uvicorn==0.29.0' boto3 && mkdir -p ~/models ~/src && echo DONE"

scp -i ~/.ssh/$KEYNAME.pem src/serve.py ubuntu@$VM_IP:~/src/serve.py
```

- [ ] Thư viện đã cài, `src/serve.py` đã ở trên EC2

> Mỗi lần sửa `src/serve.py` phải `scp` lại. Pipeline chỉ deploy **model**, không deploy
> code serving.

---

## 7. Systemd service

```bash
$SSH "sudo tee /etc/systemd/system/income-api.service > /dev/null <<EOF
[Unit]
Description=Income Model Inference Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment=\"ARTIFACT_BUCKET=$BUCKET\"
Environment=\"AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION\"
ExecStart=/usr/bin/python3 /home/ubuntu/src/serve.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable income-api"
```

Không có `GOOGLE_APPLICATION_CREDENTIALS` hay file key nào — instance profile lo phần xác
thực. **Chưa `start`**: model chưa có trên S3 cho đến khi pipeline chạy lần đầu.

- [ ] Service đã `enable`, chưa `start`

---

## 8. GitHub Secrets (đặt bằng `gh`, không cần mở trình duyệt)

```bash
CI_KEY=$(cat /tmp/ci-key.json)
python -c "
import json, sys
k = json.loads('''$CI_KEY''')['AccessKey']
print(json.dumps({'aws_access_key_id': k['AccessKeyId'],
                  'aws_secret_access_key': k['SecretAccessKey'],
                  'region': '$AWS_DEFAULT_REGION'}))" | gh secret set STORAGE_CREDENTIALS

gh secret set ARTIFACT_BUCKET --body "$BUCKET"
gh secret set SERVER_HOST     --body "$VM_IP"
gh secret set SERVER_USER     --body "ubuntu"
gh secret set SERVER_SSH_KEY  < ~/.ssh/$KEYNAME.pem

gh secret list
```

Đúng 5 secret như lab yêu cầu.

- [ ] `gh secret list` hiện đủ 5 secret

---

## 9. Chạy pipeline Bước 2

`dvc push` phải xong **trước** `git push`, nếu không CI sẽ `dvc pull` dữ liệu chưa tồn tại.

```bash
git add -A
git commit -m "feat: hoan thien train, serve, tests va pipeline CI/CD tren AWS"
dvc push
git push origin main

gh run watch                # theo dõi trực tiếp trong terminal
```

Sau khi 4 job xanh:

```bash
$SSH "sudo systemctl start income-api"

curl http://$VM_IP:8080/healthz
curl -X POST http://$VM_IP:8080/score -H "Content-Type: application/json" \
  -d '{"features": [60, 2, 5, 2, 4, 0, 1, 0, 0, 45]}'      # kỳ vọng thu_nhap_thap
curl -X POST http://$VM_IP:8080/score -H "Content-Type: application/json" \
  -d '{"features": [28, 2, 14, 2, 11, 0, 1, 0, 0, 45]}'    # kỳ vọng thu_nhap_cao
```

Nếu service không lên: `$SSH "sudo journalctl -u income-api -n 50 --no-pager"`

- [ ] 4 job xanh → ảnh `02-actions-buoc-2.png`
- [ ] Hai `curl` trả kết quả → ảnh `04-curl-api.png`
- [ ] S3 Console hiện `dvc/` và `artifacts/current/model.joblib` → ảnh `05-cloud-storage.png`

---

## 10. Bước 3 - Huấn luyện liên tục

```bash
python append_batch.py          # 22361 -> 44722 mẫu
dvc add data/train_batch1.csv
git add data/train_batch1.csv.dvc
git commit -m "data: bo sung 22361 mau du lieu moi (train_batch2)"
dvc push
git push origin main
gh run watch
```

Kết quả dự kiến (đã tính trước trên máy): `f1_score` khoảng 0.7330, `accuracy` khoảng
0.8820 — vẫn trên ngưỡng 0.65 nên Release sẽ chạy.

- [ ] Actions tự kích hoạt, commit message là commit dữ liệu → ảnh `03-actions-buoc-3.png`
- [ ] `curl` lại `/score` xác nhận model mới đang phục vụ

---

## 11. Chứng minh quality gate biết chặn (4 điểm rubric)

Làm **sau** khi đã chụp xong ảnh 02 và 03.

```bash
printf 'model: gb\nn_estimators: 50\nlearning_rate: 0.05\nmax_depth: 2\n' > params.yaml
git commit -am "test: chung minh quality gate chan model duoi nguong"
git push origin main
```

Quality Gate phải đỏ, Release bị skip → chụp `nop-bai/anh-chup-man-hinh/07-quality-gate-chan.png`.
Hoàn nguyên ngay:

```bash
printf 'model: gb\nn_estimators: 100\nlearning_rate: 0.2\nmax_depth: 3\n' > params.yaml
git commit -am "revert: tra lai bo sieu tham so tot nhat"
git push origin main
```

- [ ] Đã chụp ảnh quality gate bị chặn và đã hoàn nguyên `params.yaml`

---

## 12. Dọn dẹp sau khi được chấm (tránh hết free tier)

```bash
INSTANCE=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=income-api" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ec2 terminate-instances --instance-ids $INSTANCE
aws ec2 wait instance-terminated --instance-ids $INSTANCE
aws ec2 delete-security-group --group-name $SG
aws ec2 delete-key-pair --key-name $KEYNAME

aws s3 rb s3://$BUCKET --force

aws iam delete-user-policy --user-name income-lab-user --policy-name income-lab-bucket-access
aws iam list-access-keys --user-name income-lab-user \
  --query 'AccessKeyMetadata[].AccessKeyId' --output text | \
  xargs -n1 -I{} aws iam delete-access-key --user-name income-lab-user --access-key-id {}
aws iam delete-user --user-name income-lab-user

aws iam remove-role-from-instance-profile \
  --instance-profile-name income-api-profile --role-name income-api-role
aws iam delete-instance-profile --instance-profile-name income-api-profile
aws iam delete-role-policy --role-name income-api-role --policy-name read-current-model
aws iam delete-role --role-name income-api-role
```

- [ ] Đã xóa EC2, security group, key pair, bucket, IAM user, role, instance profile
