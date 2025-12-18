
import requests
import sys

BASE_URL = "http://localhost:8000"

def cleanup_via_api():
    print("Fetching rule groups...")
    try:
        resp = requests.get(f"{BASE_URL}/rule-groups")
        if resp.status_code != 200:
            print(f"Failed to fetch groups: {resp.text}")
            return
        
        groups = resp.json()
        print(f"Found {len(groups)} groups.")
        
        for group in groups:
            print(f"Deleting group: {group['name']} ({group['id']})")
            del_resp = requests.delete(f"{BASE_URL}/rule-groups/{group['id']}")
            if del_resp.status_code == 200:
                print("Deleted successfully.")
            else:
                print(f"Failed to delete: {del_resp.text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    cleanup_via_api()
