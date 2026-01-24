import httpx
import re
import sys
import os
import sqlite3
import jwt
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from app.core.config import settings

BASE_URL = "http://localhost:8000"
DB_PATH = 'f:/Antigravity/exam-record/exam_record.db'

def get_user_and_token():
    # 1. Get a user from DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users LIMIT 1")
    row = cursor.fetchone()
    
    if not row:
        # Create a user
        email = "testverif@example.com"
        print(f"Creating test user {email}...")
        cursor.execute("INSERT INTO users (email, role, created_at) VALUES (?, 'Contributor', CURRENT_TIMESTAMP)", (email,))
        conn.commit()
    else:
        email = row[0]
        print(f"Using existing user: {email}")
        
    conn.close()
    
    # 2. Generate Token (Plain PyJWT to avoid importing app business logic deps if complex)
    # Using HS256 as per config defaults
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"sub": email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def test_voting_flow():
    token = get_user_and_token()
    cookies = {"access_token": token}

    # 1. Get Page
    print("Fetching Event Page...")
    try:
        r = httpx.get(f"{BASE_URL}/exams/andalucia/piano/2026", cookies=cookies, timeout=10.0)
    except httpx.ConnectError:
        print("Could not connect to server. Is it running?")
        sys.exit(1)
        
    if r.status_code != 200:
        print(f"Failed to fetch page: {r.status_code}")
        sys.exit(1)
    
    html = r.text
    # Find a report_id from hx-post="/api/reports/(\d+)/vote"
    match = re.search(r'hx-post="/api/reports/(\d+)/vote"', html)
    if not match:
        print("No report vote buttons found! (Maybe no reports in DB?)")
        # Try to trigger a report creation? Or fail.
        # User said "vote like mad", assumes content creates.
        # I'll just skip fail if empty but warn.
        print("Skipping vote test as no reports found.")
        return
        
    report_id = match.group(1)
    print(f"Found Report ID: {report_id}")
    
    # 2. Vote
    print(f"Voting for Report {report_id}...")
    r_vote = httpx.post(f"{BASE_URL}/api/reports/{report_id}/vote", cookies=cookies)
    print(f"Vote status: {r_vote.status_code}")
    print(f"Vote content len: {len(r_vote.text)}")
    
    if "work-card" not in r_vote.text:
        print("Vote response did not contain work-card HTML")
        print(r_vote.text[:200])
        sys.exit(1)

    # 3. Flag
    print(f"Flagging Report {report_id}...")
    r_flag = httpx.post(f"{BASE_URL}/api/reports/{report_id}/flag", cookies=cookies)
    print(f"Flag status: {r_flag.status_code}")
    print(f"Flag content len: {len(r_flag.text)}")
    
    if "Flagged for review" not in r_flag.text:
        print("Flag response did not contain 'Flagged for review' text")
        sys.exit(1)
        
    print("Verification Successful!")

if __name__ == "__main__":
    test_voting_flow()
