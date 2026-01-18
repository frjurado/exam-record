# Design Decisions & Responses

This document records the finalized design decisions based on the review feedback and answers the open questions regarding privacy, naming, and rollout strategy.

## 1. Settled Decisions
Based on your feedback, the following are now confirmed system constraints:

*   **Region Taxonomy:** **Fixed List**. Exams are region-wide public events in Spain. We will treat the "Region" (e.g., Madrid, Andalucía) as the event container, not individual conservatories.
*   **Discipline Taxonomy:** **Fixed List**. Only specific instruments (Piano, Violin, etc.) will be supported to ensure data consistency.
*   **Moderation:** We will implement a **Flagging System** for malicious data and a **Report User** flow for bad actors.

---

## 2. Responses to Open Questions

### A. Academic Year Format
**User Question:** *"To avoid confusion, I would say just plain natural year of the exam ('2026') is easiest, but I'd like to read your thoughts about this."*

**My Opinion:** **Strongly Agree.**
*   **Reasoning:** Users think in terms of "The June Exam" or "The 2026 Exam." Using a single integer (`2026`) lowers cognitive load compared to "2025/2026."
*   **Technical Implication:** The database will store `year` as an `Integer`. All UI logic will refer to "Exam of [Year]".
*   **Edge Case:** If there are multiple calls (e.g., June vs. September), we can handle them as attributes of the same "2026 Event" or just treat them as one bucket since the repertoire list is likely valid for both. **Recommendation: Treat June/Sept as one single '2026' bucket for simplicity.**

### B. User Privacy & Naming
**User Question:** *"How would you name a user for public data? (you only have their emails). Total anonymity seems a problem... yet registering is implicit."*

**My Opinion:** **Default to Public Anonymity ("Verified Student").**
*   **Privacy First:** Students may fear backlash if they leak exam contents or if they get a consensus dispute wrong. Displaying their name adds friction.
*   **The Solution:**
    1.  **Internal Identity:** We *do* store the email and link it to a generic `User_ID`.
    2.  **Public Display:** On the frontend, we simply show: *"Source: Verified Candidate"* or *"Source: Teacher"*. We **do not** display names or pseudonyms.
    3.  **Accountability:** If a user vandalizes, other users report the *Content*. Admins see the report, look up the hidden `User_ID`, and ban that email. The public doesn't need to know *who* it was, only that the system took care of it.
    *   *Note:* This perfectly aligns with the "Low Friction" goal. No "Choose a Username" step required.

### C. Seeding & Rollout Strategy
**User Question:** *"Start small, limiting the site to a sample region & a couple of instruments. Gather help from red-life teacher contacts... What do you think?"*

**My Opinion:** **Essential for Survival.**
*   **The Network Effect Problem:** An empty database is useless. A database with 50% of Spain is hard to build. A database with **100% of Madrid Piano** is valuable immediately.
*   **Strategy:**
    *   **Phase 1 (Beta):** Hardcode the application to *only* accept/show **Madrid + Piano** (or your chosen target).
    *   **The "Teacher Seed":** Your real-life contacts are the "Stewards". Manually enter their historic data (last 5 years of exams) before public launch.
    *   **Result:** When the first real student arrives, they see a full history. They feel safe to add *their* new data because the "shelf is already full."
*   **Conclusion:** We should write this "Constrained Scope" in the Implementation Plan.
