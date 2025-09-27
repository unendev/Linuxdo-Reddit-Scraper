# test_proxy.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

print("--- Starting Gemini Proxy Connection Test ---")

# --- 1. 配置代理 (使用 V2Ray 的 HTTP 代理端口) ---
# 默认的 V2Ray HTTP 端口通常是 10809
proxy_url = "http://127.0.0.1:10809"  # <-- !!! 从 SOCKS5 改为 HTTP !!!
os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
print(f"Attempting to use HTTP proxy: {proxy_url}")

# --- 2. 加载和配置 API Key ---
# (后面的代码保持不变)
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
    print("\n[ERROR] GOOGLE_API_KEY not found.")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("API key configured.")

    # --- 3. 执行一个快速、简单的 API 调用 ---
    print("\nTesting connection by listing available models...")
    models = genai.list_models()
    gemini_pro_model = next((m for m in models if 'gemini-pro' in m.name), None)

    if gemini_pro_model:
        print("\n" + "="*40)
        print("  ✅ SUCCESS! Connection established via proxy.")
        print(f"  Successfully found model: {gemini_pro_model.name}")
        print("="*40)
    else:
        print("\n" + "="*40)
        print("  ⚠️ WARNING: Connection worked, but 'gemini-pro' model not found.")
        print("="*40)

except Exception as e:
    print("\n" + "="*40)
    print("  ❌ FAILURE! Could not connect to Gemini API.")
    print("  Error Details:")
    print(f"  {e}")
    print("\n  Troubleshooting Steps:")
    print("  1. Is your V2Ray client running and connected?")
    print("  2. Is the HTTP port 10809 correct? Check your V2Ray settings.")
    print("  3. Is there a firewall blocking Python's access to 127.0.0.1?")
    print("="*40)