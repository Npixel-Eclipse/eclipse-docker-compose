import requests
import os
import zipfile
import base64
from flask import Flask, request, send_file, render_template
from urllib.parse import quote
from datetime import datetime, timezone, timedelta


app = Flask(__name__)

KST = timezone(timedelta(hours=9))
BYTEBASE_URL = "http://bytebase.eclipsestudio.co.kr"
EMAIL = "terraform@service.bytebase.com"
SERVICE_KEY = "bbs_YGWpG85p5iMrFMqxbKYe"
PROJECT_ID = "eclipse-dev-project"
INSTANCE_ID = "eclipse-dev-instance"
INSTANCE_ID_DAILY = "daily-admin" #기존 인스턴스 ID를 재활용 하느라 인스턴스 ID가 admin 이고 인스턴스 Name은 Eclipse Diily Instance 로 되어있음.
DATABASES = [
    "bridge", "chat", "dungeon", "eclipse_admin", "fortress", "guild",
    "hunting_zone", "item", "lobby", "mail", "matchmaking",
    "notification", "pklog", "quest", "ranking", "session",
    "setting", "store", "trade"
]

# DATABASES = [
# "item"
# ]

# 토큰 획득
def get_bytebase_token():
    
    login_resp = requests.post(f"{BYTEBASE_URL}/v1/auth/login", json={
        "email": EMAIL,
        "password": SERVICE_KEY,
        "web": True
    })
    login_resp.raise_for_status()
    access_token = login_resp.cookies.get("access-token")
    if not access_token:
        raise Exception("Access token 획득 실패")
    
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

# 전체 schema 저장
def write_total_schema(db, headers, output_dir, today_str, instance_id=INSTANCE_ID):
    
    db_encoded = quote(db)
    schema_url = f"{BYTEBASE_URL}/v1/instances/{instance_id}/databases/{db_encoded}/schema"
    schema_resp = requests.get(schema_url, headers=headers)
    
    if schema_resp.status_code == 200:
        schema = schema_resp.json().get("schema", "")
        if schema:
            total_schema_filename = f"eclipse-schema-total-{today_str}-{db}.sql"
            total_schema_path = os.path.join(output_dir, total_schema_filename)
            with open(total_schema_path, "w", encoding="utf-8") as f:
                f.write(f"-- Database: {db}\n")
                f.write(f"{schema}\n\n")
            return total_schema_path, total_schema_filename
    return None, None

# changelog 저장 
def write_diff_schema(db, headers, output_dir, today_str, target_dt, instance_id=INSTANCE_ID):
    
    db_encoded = quote(db)
    changelogs_url = f"{BYTEBASE_URL}/v1/instances/{instance_id}/databases/{db_encoded}/changelogs"
    changelogs_resp = requests.get(changelogs_url, headers=headers)
    
    if changelogs_resp.status_code != 200:
        return None, None
        
    changelogs = changelogs_resp.json().get("changelogs", [])
    filtered = []
    for change in changelogs:
        try:
            created = datetime.strptime(change["createTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
            created = created.replace(tzinfo=timezone.utc).astimezone(KST)
            status = change["status"]
            if created > target_dt :
                if status == "DONE":
                    filtered.append((created, change))
        except Exception:
            continue

    if filtered:
        diff_filename = f"eclipse-schema-diff-{today_str}-{db}.sql"
        file_path = os.path.join(output_dir, diff_filename)
        filtered.reverse()
        
        with open(file_path, "w", encoding="utf-8") as f:
            try:
                for created, change in filtered:
                    sheet_uid = change.get("statementSheet")
                    issue_number = change.get("issue")
                    issue_number = issue_number.split("/")[-1]
                    if sheet_uid:
                        sheet_resp = requests.get(f"{BYTEBASE_URL}/v1/{sheet_uid}", headers=headers)
                        sheet_resp.raise_for_status()
                        full_statement = sheet_resp.json().get("content", "")
                        decoded_statement = base64.b64decode(full_statement).decode("utf-8")
                        f.write(f"-- Change on {created} Issue Number : {issue_number}\n{decoded_statement}\n\n")
            except Exception as e:
                print(f"쓰기 중 오류: {e}")
        
        return file_path, diff_filename
    return None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        target_str = request.form['target_timestamp']
        download_type = request.form.get('download_type', '다운로드')
        
        try:
            target_dt = datetime.strptime(target_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        except ValueError:
            return "잘못된 시간 형식입니다. YYYY-MM-DD HH:MM:SS 형식으로 입력하세요."

        try:
            headers = get_bytebase_token()
        except Exception as e:
            return str(e)

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        
        # 다운로드 타입에 따라 인스턴스 ID 선택
        instance_id = INSTANCE_ID_DAILY if download_type == "Daily 다운로드" else INSTANCE_ID
        
        zip_filename = f"eclipse-schema-info-{today_str}-{download_type}.zip"
        zip_path = os.path.join(output_dir, zip_filename)
        
        try:
            os.remove(zip_path)
        except Exception as e:
            print(f"error {e}")
            
        sql_file_paths = []

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for db in DATABASES:
                # total
                total_path, total_filename = write_total_schema(db, headers, output_dir, today_str, instance_id)
                if total_path:
                    zipf.write(total_path, arcname=total_filename)
                    sql_file_paths.append(total_path)
                
                # diff
                diff_path, diff_filename = write_diff_schema(db, headers, output_dir, today_str, target_dt, instance_id)
                if diff_path:
                    zipf.write(diff_path, arcname=diff_filename)
                    sql_file_paths.append(diff_path)

        # 개별 sql 정리
        for file_path in sql_file_paths:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"파일 삭제 중 오류: {e}")

        return send_file(zip_path, as_attachment=True)

    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5010)

