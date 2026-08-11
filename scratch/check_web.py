import urllib.request
import json
import sys

def check_url(url):
    try:
        print(f"Requesting GET {url} ...")
        response = urllib.request.urlopen(url, timeout=3.0)
        code = response.getcode()
        content = response.read().decode('utf-8')
        print(f"-> Response: {code} OK (Length: {len(content)} bytes)")
        if "application/json" in response.headers.get("Content-Type", ""):
            print(f"-> JSON Payload: {json.dumps(json.loads(content)[:2] if isinstance(json.loads(content), list) else json.loads(content), indent=2, ensure_ascii=False)}")
        return True
    except Exception as e:
        print(f"-> LỖI khi kết nối tới {url}: {e}", file=sys.stderr)
        return False

def main():
    print("=== KIỂM TRA WEB SERVER VÀ API ENDPOINTS ===")
    
    # Check index html
    check_url("http://127.0.0.1:8000/")
    
    # Check static styles/js
    check_url("http://127.0.0.1:8000/static/style.css")
    check_url("http://127.0.0.1:8000/static/app.js")
    
    # Check analytics API
    check_url("http://127.0.0.1:8000/api/analytics/summary")
    check_url("http://127.0.0.1:8000/api/analytics/products")
    check_url("http://127.0.0.1:8000/api/analytics/hourly")

if __name__ == "__main__":
    main()
