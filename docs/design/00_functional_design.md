# Product Design Overview: Exam Record

**Version:** 1.0 (Initial Design)
**Project Scope:** Web Application for Crowdsourcing Music Conservatory Entrance Exams

---

## 1. Executive Summary
**Exam Record** is a community-driven database designed to solve the lack of transparency in music conservatory entrance exams (specifically Music Analysis).

Currently, exam content (which work was analyzed) is lost immediately after the exam, leaving future students and teachers in the dark. This platform allows candidates to crowdsource this historical data, using a consensus-based model to validate truth without heavy administrative moderation.

**Core Value Proposition:**
* **For Students:** Reduces anxiety by revealing historical trends ("What does Madrid usually ask?").
* **For Teachers:** Saves research time with verified repertoire lists.
* **For the Community:** Democratizes access to elite educational information.

---

## 1A. Rollout Strategy (Beta Phase)
To ensure immediate value, the initial launch will be **constrained** to build density.
*   **Scope:** Restricted to **Andalucía** (Region) + **Piano** (Discipline).
*   **Seeding:** We will pre-populate the database with ~5 years of historic data from "Stewards" (trusted teachers) before opening to the public.
*   **Expansion:** New regions/disciplines will be unlocked only when sufficient localized seed data is available.

---

## 2. Design Philosophy
The system is built on three pillars to handle the specific challenges of musical metadata and user behavior:

1.  **Standardization over Creation:** We aggressively guide users toward canonical data (OpenOpus/Wikidata) to prevent a "metadata mess," only allowing raw text entry as a last resort.
2.  **Trust via Consensus:** We replace binary "Moderator Verification" with a dynamic "Consensus Score" (Traffic Light System). Truth emerges from agreement, not authority.
3.  **Low-Friction Contribution:** We recognize students are transient users. We capture data through "Magic Links" and "Lazy" forms, minimizing barriers to entry.

---

## 3. Core Feature Specifications

### 3.1 The Contribution Engine (Data Entry)
*The critical path. Bad data in = broken system.*

* **Composer Selection:**
    * **Level 1 (Client-Side):** Instant autocomplete from a cached "Top 500" list.
    * **Level 2 (API Check):** If unknown, query **Wikidata** to confirm identity before adding to DB.
    * **Level 3 (Unverified):** Allow raw entry only if external checks fail (flagged as `Unverified`).
* **Work Selection:**
    * **Alias Search:** Users can search by Nickname ("Moonlight"), Catalog ("Op. 27"), or Title. System matches against **OpenOpus**.
    * **The "Lazy Builder":** If the work is missing, users build it via a structured form (Genre + Key + Number). The system treats these inputs as filters to try and match existing works one last time before creating a new ID.
* **Granularity:** Mandatory selector for *Whole Work* vs. *Specific Movement* vs. *Excerpt*.

### 3.2 The Trust Protocol (Validation)
*How we handle conflicting reports without a moderator.*

* **Metric:** **Consensus Rate** (% of agreement on the top answer).
  $$Consensus Rate = \frac{Votes for Top Answer}{Total Votes}$$
* **Visual States:**
    * 👤 **Single Source:** Only 1 vote. (Neutral/Gray). *Message: "Waiting for confirmation."*
    * ✅ **Verified:** $\ge$ 2 votes AND > 75% consensus. (Green). *Message: "Verified by community."*
    * ⚠️ **Disputed:** $\ge$ 2 votes AND < 75% consensus. (Red/Orange). *Message: "Conflicting reports."*
* **Resolution:** Disputed entries show the top 2 conflicting answers side-by-side, allowing the community to vote/comment to resolve it.

### 3.3 The Browse Experience
* **Global Search:** "Madrid 2023 Analysis".
*   **Filtering:** By Region (Fixed List), Discipline (Fixed List e.g., Piano/Violin), and Year.
* **Interaction:**
    * **"I did this exam":** A single-click button that adds a vote to an existing entry (Validation).
    * **"Propose Correction":** Opens the input form to submit an alternative answer (Dispute).

### 3.4 The Motivation Loop (Retention & Growth)
* **The "Trojan Horse" (Candidates):**
    * Users subscribe to **"Exam Alerts"** (Email capture) before the exam season.
    * **Trigger:** System emails them immediately after the exam window: *"How was it? Tell us what fell."*
* **The "Maestro" Strategy (Teachers):**
    * Teachers gain **"Steward"** status by verifying data.
    * **Incentive:** Unlocks **PDF Export** (clean, printable historical lists for lesson prep) and "Top Contributor" badges for professional reputation.

---

## 4. User Architecture

| Role | Definition | Capabilities | Transition Path |
| :--- | :--- | :--- | :--- |
| **Visitor** | Anonymous / Lurker | Search, Browse, View Validation Status. | Default state. |
| **Contributor** | Verified Email | Submit Data, Create Works, **Vote (Confirm)**. | Via "Get Alerts" or "Submit Data" (Magic Link). |
| **Steward** | Teacher / Power User | **Dispute Resolution**, **PDF Export**, Merge Requests. | Via "Claim Teacher Profile" + Contribution Threshold. |
| **Admin** | System Owner | Hard Delete, Global Merge, Ban User. | N/A |

---

## 5. Technical Design Notes
* **Identity:** Passwordless authentication (Magic Links) is preferred to reduce friction for one-time student contributors.
* **Data Structure:**
    * `Work_ID`: Unique ID for the musical piece (e.g., *Beethoven Sonata 1*).
    * `Exam_Event_ID`: Unique ID for the specific event (e.g., *Madrid-Piano-2026*). Note: Year is the **Natural Year** of the exam (Integer), not the academic range.
    * `Exam_Entry`: The link between Event and Work (The user's submission).
* **External Dependencies:**
    * **OpenOpus API** (Mirrored locally for performance).
    * **Wikidata API** (Real-time fallback for composers).
