import requests
import time
import os

API_BASE = "http://localhost:8000/api/v1"

def log(msg):
    print(msg)
    with open("chunking_verification.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_chunking():
    # Clear log
    with open("chunking_verification.txt", "w", encoding="utf-8") as f:
        f.write("Starting Chunking Verification...\n")

    log("1. Creating dummy document...")
    filename = "test_chunking.txt"
    content = "This is a test document.\nIt has multiple lines.\nAnd some sentences. This is sentence 4. This is sentence 5."
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
        
    log("2. Uploading document...")
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "text/plain")}
        try:
            res = requests.post(f"{API_BASE}/documents", files=files)
        except Exception as e:
            log(f"Upload request failed: {e}")
            return
        
    if res.status_code != 200:
        log(f"Upload failed: {res.text}")
        return
        
    doc = res.json()
    doc_id = doc["id"]
    log(f"   Document uploaded: {doc_id}")
    
    log("3. Waiting for processing...")
    for i in range(10):
        time.sleep(2)
        try:
            res = requests.get(f"{API_BASE}/documents/{doc_id}")
            doc = res.json()
            log(f"   Status: {doc['status']}")
            if doc['status'] == 'INDEXED':
                break
            if doc['status'] == 'FAILED':
                log("   Processing failed!")
                return
        except Exception as e:
            log(f"Status check failed: {e}")
            
    if doc['status'] != 'INDEXED':
        log("   Timeout waiting for processing")
        return
        
    log("4. Fetching chunks...")
    try:
        res = requests.get(f"{API_BASE}/documents/{doc_id}/chunks")
        if res.status_code != 200:
            log(f"Failed to fetch chunks: {res.text}")
            return
            
        chunks = res.json()
        log(f"   Fetched {len(chunks)} chunks")
        
        if len(chunks) > 0:
            log(f"   First chunk content: {chunks[0]['content']}")
            log(f"   First chunk stats: {chunks[0]['word_count']} words, {chunks[0]['sentence_count']} sentences")
            log("SUCCESS: Chunking verification passed.")
        else:
            log("FAIL: No chunks found.")
    except Exception as e:
        log(f"Fetch chunks failed: {e}")
        
    # Cleanup
    try:
        os.remove(filename)
        requests.delete(f"{API_BASE}/documents/{doc_id}")
    except:
        pass

if __name__ == "__main__":
    try:
        test_chunking()
    except Exception as e:
        log(f"Test failed: {e}")
