# Email Provider Options for Exam Record

For Phase 5.2, we need a reliable way to send "Magic Links" to users. Here is an analysis of the best options for a Python/FastAPI application hosted on Fly.io.

## 1. Resend (Recommended)
A modern email API designed for developers. It wraps Amazon SES but with a much better DX (Developer Experience).

*   **Pros:**
    *   **Extremely easy setup**: Python SDK is simple (`pip install resend`).
    *   **Generous Free Tier**: 3,000 emails/month (100/day limit usually), which is perfect for Beta.
    *   **Fast Fly.io integration**: Works great in containerized environments.
    *   **Clean UI**: Great dashboard for tracking logs and delivery status.
*   **Cons:**
    *   Newer player, but very stable.
*   **Verdict**: **Best choice for this project.**

## 2. SendGrid (Industry Standard)
The traditional heavyweight in transactional email.

*   **Pros:**
    *   **Battle-tested**: Used by massive companies (Uber, Spotify).
    *   **Rich Features**: Template engine, complex analytics.
*   **Cons:**
    *   **Strict Verification**: Account approval can sometimes be finicky for new domains.
    *   **Free Tier**: 100 emails/day forever.
    *   **Complexity**: API is slightly more verbose than Resend.
*   **Verdict**: **Solid backup choice.**

## 3. Amazon SES (Raw AWS)
Directly using AWS Simple Email Service.

*   **Pros:**
    *   **Cheapest**: $0.10 per 1,000 emails. Unbeatable at scale.
    *   **Reliability**: It's AWS.
*   **Cons:**
    *   **High Complexity**: Requires AWS IAM setup, region configuration, and domain verification (DNS DKIM/SPF).
    *   **Sandbox**: You start in a "Sandbox" where you can only email verified addresses until you request a limit increase (manual support ticket).
*   **Verdict**: **Overkill for now.** Switch to this only if you scale to >50k emails/month.

## 4. SMTP (Gmail/Outlook)
Using a personal or business email account via SMTP.

*   **Pros:**
    *   Free (if you already have the account).
*   **Cons:**
    *   **Not for Apps**: Rate limits (e.g., 500/day for Gmail) will block you quickly.
    *   **Security**: Requires "App Passwords" and often gets flagged as spam.
    *   **Slow**: SMTP is synchronous and slow compared to HTTP APIs.
*   **Verdict**: **Avoid for production applications.**

## Summary & Recommendation

I recommend using **Resend**.
1.  It has a Python SDK that fits perfectly with FastAPI.
2.  The free tier covers our Beta needs (up to 3,000 verifications/month).
3.  Setup is just adding an API Key.

### Next Steps for Phase 5.2
1.  Sign up for [Resend](https://resend.com) (or chosen provider).
2.  Verify the domain (`exam-record.com` or similar).
3.  Get the API Key.
4.  Update `.env` and `app/core/config.py`.
5.  Replace the console logging in `auth.py` with the actual email sending call.
