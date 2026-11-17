import json
import urllib.request
import urllib.error

def test_login(base_url, email, password, expect_success=True):
    url = f"{base_url}/api/v1/auth/login"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status_code = resp.status
            # Sanitize token
            has_token = bool(data.get("access_token"))
            token_type = data.get("token_type")
            user_email = data.get("user", {}).get("email")
            user_id = data.get("user", {}).get("id")
            cookies = resp.headers.get_all("Set-Cookie") or []
            cookie_names = [c.split(";")[0].split("=")[0] for c in cookies]
            print(f"[{base_url}] Login SUCCESS: status={status_code}, has_token={has_token}, type={token_type}, user={user_email}, user_id={user_id}, cookies={cookie_names}")
            assert status_code == 200
            assert has_token is True
            assert user_email == email.lower()
            return True, status_code, "Login successful with token issued"
    except urllib.error.HTTPError as err:
        status_code = err.code
        body = err.read().decode("utf-8")
        try:
            err_json = json.loads(body)
            err_msg = err_json.get("error", {}).get("message") or err_json.get("detail")
            err_code = err_json.get("error", {}).get("code")
        except Exception:
            err_msg = body
            err_code = None
        print(f"[{base_url}] Login EXPECTED/CAUGHT HTTPError: status={status_code}, code={err_code}, msg={err_msg}")
        if not expect_success:
            assert status_code == 401
            return True, status_code, f"Correctly rejected: {err_msg}"
        return False, status_code, f"Unexpected failure: {err_msg}"

def run():
    print("--- TEST 1: Direct Backend Login (Alice) on http://127.0.0.1:8000 ---")
    ok1, code1, msg1 = test_login("http://127.0.0.1:8000", "alice@dropsafe.local", "AlicePass123!", expect_success=True)
    
    print("\n--- TEST 2: Vite Proxy Login (Alice) on http://localhost:5173 ---")
    ok2, code2, msg2 = test_login("http://localhost:5173", "alice@dropsafe.local", "AlicePass123!", expect_success=True)

    print("\n--- TEST 3: Invalid Credentials Rejection on http://localhost:5173 ---")
    ok3, code3, msg3 = test_login("http://localhost:5173", "alice@dropsafe.local", "WrongPassword999!", expect_success=False)

    print("\n--- TEST 4: Non-existent User Rejection on http://localhost:5173 ---")
    ok4, code4, msg4 = test_login("http://localhost:5173", "nonexistent@dropsafe.local", "AnyPassword123!", expect_success=False)

    print("\nSummary:")
    print("Test 1 (Direct Backend Login):", "PASS" if ok1 else "FAIL")
    print("Test 2 (Proxy Login):", "PASS" if ok2 else "FAIL")
    print("Test 3 (Invalid Password):", "PASS" if ok3 else "FAIL")
    print("Test 4 (Non-existent User):", "PASS" if ok4 else "FAIL")

if __name__ == "__main__":
    run()
