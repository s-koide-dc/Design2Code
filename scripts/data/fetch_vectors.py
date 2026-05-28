import os
import urllib.request
import tarfile
import shutil
import ssl
import sys

sys.path.append(os.getcwd())

from src.utils.cli_output import emit_error, emit_progress

# chiVe v1.3 mc90 (Aligned with config_manager default)
DEFAULT_VECTOR_URL = "https://sudachi.s3-ap-northeast-1.amazonaws.com/chive/chive-1.3-mc90.tar.gz"
EXPECTED_TXT = "chive-1.3-mc90.txt"

def fetch_vectors():
    vector_url = os.environ.get("VECTOR_URL_OVERRIDE", DEFAULT_VECTOR_URL)
    resources_dir = os.path.join(os.getcwd(), 'resources', 'vectors')
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    tar_name = os.path.basename(vector_url)
    tar_path = os.path.join(resources_dir, tar_name)
    
    emit_progress(f"Downloading vectors from {vector_url}...")
    
    # Bypass SSL verification if needed (sometimes local certs are missing)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(vector_url, context=ssl_ctx) as response, open(tar_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        emit_progress("Download complete.")
        
        emit_progress("Extracting vectors...")
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(path=resources_dir)
            
        emit_progress(f"Vectors extracted to {resources_dir}")
        expected_path = os.path.join(resources_dir, EXPECTED_TXT)
        if not os.path.exists(expected_path):
            nested_path = os.path.join(resources_dir, "chive-1.3-mc90", EXPECTED_TXT)
            if os.path.exists(nested_path):
                shutil.copy2(nested_path, expected_path)
                emit_progress(f"Placed vector file at {expected_path}")
        if not os.path.exists(expected_path):
            emit_error(f"警告: 想定したベクトルファイルが見つかりません: {expected_path}")
            emit_error("アーカイブの内容を確認するか、EXPECTED_TXT を更新してください。")
        return 0
        
    except Exception as e:
        emit_error(f"エラー: ベクトルのダウンロードまたは展開に失敗しました: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(fetch_vectors())
