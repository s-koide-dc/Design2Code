import os
import urllib.request
import gzip
import shutil
import sys

sys.path.append(os.getcwd())

from src.utils.cli_output import emit_error, emit_progress

# URL for JMdict (English)
# Using the main mirror
DEFAULT_JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"

def fetch_jmdict():
    jmdict_url = os.environ.get("JMDICT_URL_OVERRIDE", DEFAULT_JMDICT_URL)
    resources_dir = os.path.join(os.getcwd(), 'resources')
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    gz_path = os.path.join(resources_dir, 'JMdict_e.gz')
    xml_path = os.path.join(resources_dir, 'JMdict_e.xml')
    
    emit_progress(f"Downloading JMdict from {jmdict_url}...")
    
    try:
        # Download
        with urllib.request.urlopen(jmdict_url) as response, open(gz_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        emit_progress("Download complete.")
        
        # Decompress
        emit_progress("Decompressing JMdict...")
        with gzip.open(gz_path, 'rb') as f_in:
            with open(xml_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        emit_progress(f"Saved to {xml_path}")
        return 0
        
    except Exception as e:
        emit_error(f"エラー: JMdict のダウンロードまたは展開に失敗しました: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(fetch_jmdict())
