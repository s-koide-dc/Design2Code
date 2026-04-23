import os
import urllib.request
import tarfile
import shutil
import ssl

# chiVe v1.3 mc90 (Aligned with config_manager default)
VECTOR_URL = "https://sudachi.s3-ap-northeast-1.amazonaws.com/chive/chive-1.3-mc90.tar.gz"
EXPECTED_TXT = "chive-1.3-mc90.txt"

def fetch_vectors():
    resources_dir = os.path.join(os.getcwd(), 'resources', 'vectors')
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    tar_name = os.path.basename(VECTOR_URL)
    tar_path = os.path.join(resources_dir, tar_name)
    
    print(f"Downloading vectors from {VECTOR_URL}...")
    
    # Bypass SSL verification if needed (sometimes local certs are missing)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(VECTOR_URL, context=ssl_ctx) as response, open(tar_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Download complete.")
        
        print("Extracting vectors...")
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(path=resources_dir)
            
        print(f"Vectors extracted to {resources_dir}")
        expected_path = os.path.join(resources_dir, EXPECTED_TXT)
        if not os.path.exists(expected_path):
            nested_path = os.path.join(resources_dir, "chive-1.3-mc90", EXPECTED_TXT)
            if os.path.exists(nested_path):
                shutil.copy2(nested_path, expected_path)
                print(f"Placed vector file at {expected_path}")
        if not os.path.exists(expected_path):
            print(f"Warning: expected vector file not found: {expected_path}")
            print("Check the archive contents or update EXPECTED_TXT if the name differs.")
        return True
        
    except Exception as e:
        print(f"Error downloading/extracting vectors: {e}")
        return False

if __name__ == "__main__":
    fetch_vectors()
