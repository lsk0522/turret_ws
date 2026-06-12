import paramiko
import os
import sys

# ── 연결 정보 ──────────────────────────────────────────────
HOST     = "172.30.14.31"
PORT     = 22
USERNAME = "pi30306"
PASSWORD = "12345678"

LOCAL_DIR  = os.path.dirname(os.path.abspath(__file__)) + r"\turret_ws"
REMOTE_DIR = "/home/pi30306/turret_ws"

# 전송 제외 목록
EXCLUDE_DIRS  = {"turret_venv", "__pycache__", "picture", ".git"}
EXCLUDE_FILES = {".pyc", ".pyo"}

# ──────────────────────────────────────────────────────────

def should_skip(name, is_dir=False):
    if is_dir and name in EXCLUDE_DIRS:
        return True
    if not is_dir and any(name.endswith(ext) for ext in EXCLUDE_FILES):
        return True
    return False

def upload_dir(sftp, local_path, remote_path):
    """재귀적으로 폴더 전송"""
    # 원격 디렉토리 생성
    try:
        sftp.mkdir(remote_path)
        print(f"[디렉토리 생성] {remote_path}")
    except IOError:
        pass  # 이미 존재하면 무시

    for item in os.listdir(local_path):
        local_item  = os.path.join(local_path, item)
        remote_item = remote_path + "/" + item

        if os.path.isdir(local_item):
            if should_skip(item, is_dir=True):
                print(f"[건너뜀] {local_item}")
                continue
            upload_dir(sftp, local_item, remote_item)
        else:
            if should_skip(item):
                print(f"[건너뜀] {local_item}")
                continue
            print(f"[전송] {local_item}  →  {remote_item}")
            sftp.put(local_item, remote_item)

def main():
    print(f"연결 중: {USERNAME}@{HOST}:{PORT}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(HOST, PORT, USERNAME, PASSWORD, timeout=10)
        print("SSH 연결 성공!\n")

        sftp = client.open_sftp()

        # 원격 루트 디렉토리 생성
        try:
            sftp.mkdir(REMOTE_DIR)
            print(f"[루트 디렉토리 생성] {REMOTE_DIR}")
        except IOError:
            print(f"[루트 디렉토리 이미 존재] {REMOTE_DIR}")

        upload_dir(sftp, LOCAL_DIR, REMOTE_DIR)

        sftp.close()
        client.close()
        print("\n✅ 전송 완료!")

    except paramiko.AuthenticationException:
        print("❌ 인증 실패: 아이디/비밀번호를 확인하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
