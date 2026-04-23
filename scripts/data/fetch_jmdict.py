import os
import urllib.request
import gzip
import shutil

# URL for JMdict (English)
# Using the main mirror
JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"

def fetch_jmdict():
    resources_dir = os.path.join(os.getcwd(), 'resources')
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    gz_path = os.path.join(resources_dir, 'JMdict_e.gz')
    xml_path = os.path.join(resources_dir, 'JMdict_e.xml')
    
    print(f"Downloading JMdict from {JMDICT_URL}...")
    
    try:
        # Download
        with urllib.request.urlopen(JMDICT_URL) as response, open(gz_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Download complete.")
        
        # Decompress
        print("Decompressing JMdict...")
        with gzip.open(gz_path, 'rb') as f_in:
            with open(xml_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"Saved to {xml_path}")
        return True
        
    except Exception as e:
        print(f"Error downloading/processing JMdict: {e}")
        return False

if __name__ == "__main__":
    fetch_jmdict()
