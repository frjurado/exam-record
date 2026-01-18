# Design Specification: Motivation & Incentive System

## 1. Overview
The sustainability of the Exam Record depends on a continuous stream of fresh data. Since the primary user (the Candidate) has a short lifecycle (churns after the exam), we must use **Pre-Commitment strategies** for candidates and **Reputation strategies** for Teachers (the permanent user base).

---

## 2. The Candidate Strategy: "The Time Capsule"

### Phase 1: The Hook (Pre-Exam)
* **User Need:** Anxiety reduction. "I need to know as soon as info is available."
* **Feature:** **"Exam Alerts"**
* **UI Component:** A sticky widget or modal on search results.
    * *Copy:* "Taking the entrance exam in [Region] this year? Get notified instantly when new analysis works are reported."
    * *Input:* Email Address.

### Phase 2: The Nudge (Exam Window)
* **Trigger:** The system detects the approximate date of exams (based on historical data or user reports).
* **Action:** Automated Email Campaign.
    * **Email 1 (Morning of):** "Good luck!" (Pure empathy).
    * **Email 2 (24h later):** "Be the first to report."
    * *Copy:* "How did it go? 300 students are waiting to know what work was chosen. take 30 seconds to help them."
    * *Link:* Direct "One-Click" token link to the **Data Input Form** (No login required to minimize friction).

---

## 3. The Teacher Strategy: "The Expert Hub"

### Motivation Profile
Teachers are "Power Users" who return annually. They need **Prestige** and **Efficiency**.

### Feature: Verified Contributor Badges
* **Mechanism:** Users identified as teachers who consistently provide verified data (or whose data is verified by consensus).
* **Visual Reward:** "Top Contributor [Year]" badge on their profile.
* **Value:** Acts as marketing/social proof for their private teaching practice.

### Feature: The "Repertoire Cheat Sheet" (Utility)
* **Problem:** Teachers spend hours compiling lists of "past exams" to drill their students.
* **Solution:** **"Export to PDF"**.
* **Gate:** This feature is locked.
* **Key:** Unlock by contributing 1 new exam record or verifying 3 existing records.
* **Result:** Transforms a "freeloader" teacher into an active maintainer of the database.

---

## 4. Summary of Triggers

| User Role | Motivation | Trigger Point | Incentive |
| :--- | :--- | :--- | :--- |
| **Candidate** | Anxiety / FOMO | Pre-Exam Search | "Get Alerts" (Captures Email) |
| **Teacher** | Efficiency | Lesson Prep | "Download PDF Summary" (Requires Contribution) |
| **Teacher** | Reputation | Community Browsing | "Verified Expert" Badge |
