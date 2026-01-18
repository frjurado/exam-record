# Design Specification: User Roles & Permissions

## 1. Overview
The User Role system is designed to support the three pillars of the application:
1.  **Democratization:** Maximum access for anonymous users.
2.  **Low Friction:** Passwordless/Token-based entry for one-time contributors.
37.  **Sustainability:** Utility-based incentives for long-term power users (Teachers).
    
    ## 1A. Privacy & Anonymity Policy
    *   **Public Display:** All Users are **Publicly Anonymous**. We do not display usernames. Contributions are attributed to generic labels (e.g., *"Verified Candidate"*, *"Steward"*).
    *   **Internal Accountability:** Emails are linked to a hidden `User_ID`. This allows Admins to ban bad actors without exposing users to public scrutiny.

## 2. Role Definitions

| Role | Type | Access Level | Primary Motivation |
| :--- | :--- | :--- | :--- |
| **Visitor** | Anonymous | Read-Only | Information Consumption |
| **Contributor** | Verified Email | Read + Write + Vote | Alerts & Curiosity |
| **Steward** | Verified Profile | Power Tools | Reputation & Utility (PDFs) |
| **Admin** | System Owner | God Mode | Maintenance |

---

## 3. Detailed Permissions Matrix

| Feature | Visitor | Contributor | Steward |
| :--- | :---: | :---: | :---: |
| **Search & Browse** | ✅ | ✅ | ✅ |
| **View Validation Tags** | ✅ | ✅ | ✅ |
| **Get Exam Alerts** | ❌ (Triggers Signup) | ✅ | ✅ |
| **Submit New Exam** | ❌ (Triggers Signup) | ✅ | ✅ |
| **Create New Work** | ❌ | ✅ (Ambiguous OK) | ✅ (Clean Data) |
| **Vote (Confirm)** | ❌ | ✅ (Weight: 1) | ✅ (Weight: 1) |
| **Propose Correction** | ❌ | ✅ | ✅ |
| **Export Data (PDF)** | ❌ | ❌ | ✅ |
| **Merge Duplicates** | ❌ | ❌ | ⚠️ (Request Only) |
| **Flag Content** | ❌ | ✅ | ✅ |

---

## 4. Lifecycle & Transitions

### From Visitor to Contributor (The "Hook")
* **Mechanism:** The user is never asked to "Register." They are asked to **"Subscribe to Alerts"** or **"Share their Result."**
* **Tech:** These actions require an email. The system validates the email (Magic Link) and implicitly creates a Contributor account.

### From Contributor to Steward (The "Upsell")
* **Mechanism:** The user encounters a restricted high-value feature (PDF Export or Teacher Leaderboard).
* **Requirement:** To access, they must "Complete Profile" (mark as Teacher) and perform a set number of **Community Actions** (Voting/Verifying).

## 5. Security & Trust Notes
* **Vote Manipulation:** By requiring email verification for the "Contributor" role, we prevent simple script-kiddie spamming of votes.
* **Steward Verification:** Initially, "Steward" status is self-declared but reputation-gated (must contribute to unlock features). This avoids the administrative burden of manually checking music degrees.
