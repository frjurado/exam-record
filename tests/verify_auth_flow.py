import httpx
import sys
import os
sys.path.append(os.getcwd())

BASE_URL = "http://127.0.0.1:8000"
USER_EMAIL = "test@example.com"

def get_auth_cookie():
    # 1. Request Magic Link
    print(f"Requesting Magic Link for {USER_EMAIL}...")
    r = httpx.post(f"{BASE_URL}/api/auth/magic-link", json={"email": USER_EMAIL})
    print(r.json())
    
    # 2. Get the link from the server logs (simulated here since we know the secret)
    # Actually, simpler: just generate a valid token manually if possible, or parse the log?
    # Parsing logs is hard.
    # We can use the /auth/verify endpoint if we knew the token.
    # Wait, the server prints it. I can't read the server stdout easily here easily while it runs in background.
    # BUT, I can use the same code as the server to generate a token if I have access to the secret key.
    # Let's assume the previous `manual_verify_voting.py` logic worked because it reused a session or we hardcoded something?
    # Ah, `manual_verify_voting.py` didn't implement full auth, it just assumed we had cookies or... wait, how did it work?
    # It imported `app.core.security`! So it generated a token locally. I should do that.
    return generate_local_cookie()

def generate_local_cookie():
    from app.core import security, config
    from datetime import timedelta
    
    access_token = security.create_access_token(
        data={"sub": USER_EMAIL, "role": "Visitor"},
        expires_delta=timedelta(minutes=15)
    )
    return {"access_token": access_token}


def verify():
    # 1. Unauthenticated Vote
    print("\n--- Testing Unauthenticated Vote ---")
    try:
        r = httpx.post(f"{BASE_URL}/api/reports/1/vote", timeout=5.0)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)
        
    print(f"Status: {r.status_code}")
    if "auth-modal" in r.text:
        print("SUCCESS: Returned Auth Modal")
    else:
        print("FAILURE: Did not return Auth Modal")
        print(r.text[:200])
        sys.exit(1)

    # 2. Authenticated Vote
    print("\n--- Testing Authenticated Vote ---")
    cookies = generate_local_cookie()
    r = httpx.post(f"{BASE_URL}/api/reports/1/vote", cookies=cookies, timeout=5.0)
    
    print(f"Status: {r.status_code}")
    if "consensus-banner" in r.text and "work-card" in r.text:
        print("SUCCESS: Returned Banner (OOB) and Work Card")
    else:
        print("FAILURE: Validation failed")
        if "consensus-banner" not in r.text: print("- Missing Banner")
        if "work-card" not in r.text: print("- Missing Work Card")
        print(r.text[:500])
        sys.exit(1)

if __name__ == "__main__":
    verify()
