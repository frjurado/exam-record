# Design Specification: Validation & Dispute Resolution System

## 1. Overview
The goal of this system is to determine the trustworthiness of exam data crowdsourced from students. Since we cannot manually verify every entry, we rely on a **Consensus Model**.

This model shifts the metric of trust from **Volume** (how many votes) to **Agreement** (the ratio of matching votes). This ensures that low-volume disciplines (e.g., Tuba, Harp) can achieve "Verified" status just as easily as high-volume disciplines (Piano, Violin).

---

## 2. The Logic: "Consensus Score"

Trust is calculated dynamically based on the votes cast for a specific Exam Event (unique combination of Year + Region + Discipline).

### Formula
$$\text{Consensus Rate} = \frac{\text{Votes for Top Answer}}{\text{Total Votes for Exam}}$$

### The Three Trust States

#### State A: "Single Source" (Neutral) 👤
* **Definition:** Data exists, but relies on the word of a single user.
* **Trigger Condition:** Total Votes = 1.
* **Visual Logic:** Gray Badge / Neutral Icon.
* **User Message:** *"Waiting for confirmation."*

#### State B: "Verified" (Trusted) ✅
* **Definition:** The community has reached a high level of agreement on this work.
* **Trigger Condition:**
    1.  Total Votes $\ge$ 2
    2.  Consensus Rate $\ge$ 75%
* **Visual Logic:** Green Checkmark / Bold Text.
* **User Message:** *"Verified by students."*
* **Example:** 2 votes total, both for Work A. (100% Consensus).

#### State C: "Disputed" (Warning) ⚠️
* **Definition:** Users have submitted conflicting information.
* **Trigger Condition:**
    1.  Total Votes $\ge$ 2
    2.  Consensus Rate $<$ 75%
* **Visual Logic:** Orange or Red Warning Badge.
* **User Message:** *"Conflicting reports. Please check details."*
* **Display:** The system must show the Top 2 competing answers with their percentages (e.g., "60% say Sonata A / 40% say Sonata B").

---

## 3. User Interface & Interaction

### The "Confirm" Action (Voting)
To increase data points without requiring full data entry, we use a low-friction confirmation mechanism.

* **Scenario:** User views an exam page for "Madrid 2023 - Piano".
* **View:** They see "Beethoven - Sonata No. 14" listed.
* **Action Button:** A prominent button labeled **"I did this exam too"** or **"Confirm"**.
* **Logic:** Clicking this button increments the vote count for that specific entry by +1.

### The "Correct" Action (Disputing)
* **Scenario:** User views the same page but believes the entry is wrong.
* **Action Button:** A secondary text link or button: **"Propose a correction"**.
* **Logic:** Opens the **Data Input Modal** (see Data Input Spec).
    * If they submit a *different* work, it creates a second entry for that exam.
    * The "Consensus Rate" is immediately recalculated, likely triggering the **"Disputed"** state.

---

## 4. Edge Cases & Resilience

### The "Troll" Scenario
* **Situation:** A real entry exists (1 vote). A troll adds a fake entry (1 vote).
* **Result:** Total Votes = 2. Consensus = 50%.
* **System State:** **Disputed ⚠️**.
* **Why this works:** The system correctly identifies that the truth is unclear. It warns the next student to be careful. The next real student (Vote #3) will likely vote for the Real Entry, pushing Consensus to 66% (still disputed) or eventually 75%+ (Verified).

### The "Year" Duplicate
* **Situation:** One user enters "2023", another enters "2023-2024".
* **Resolution:** Dates are standardized to the **Natural Year** (Integer). "2023-2024" or "June 2024" are both stored as `2024`.

### The "Same Work, Different Name"
* **Situation:** User A enters "Moonlight Sonata". User B enters "Sonata 14".
* **Resolution:** Relies on the **Data Input System** (OpenOpus ID matching). If the Input System fails and creates two distinct IDs, they appear as a Dispute.
* **Fix:** Admin or High-Reputation User "Merge" tool (future feature).

### The "Malicious Actor" (Vandalism)
* **Situation:** Users spamming fake data or abusive content.
* **Resolution:**
    1.  **Flagging:** Any user can flag an entry as "Spam/Abusive".
    2.  **Removal:** Admins review flagged content.
    3.  **Banning:** Admins can ban the underlying email (User ID) associated with the malicious entries. (Note: Usernames are not displayed publicly, preserving privacy while maintaining accountability).