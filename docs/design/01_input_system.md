# Design Specification: Exam Record Data Input System

## 1. Overview
The goal of this system is to balance **low friction for students** (who are entering data post-exam) with **high data integrity** (required for the platform to be useful).

The system prioritizes **Standardization over Creation**. We guide users toward existing canonical data (from internal or external sources) and only allow "raw" text entry as a verified fallback.

### Core Principles
* **Client-Side Intelligence:** Immediate feedback using cached "Top" lists to reduce server load and latency.
* **External Sources of Truth:** Utilization of **Wikidata** (Composers) and **OpenOpus** (Works) to validate inputs.
* **The "Lazy Builder":** Complex data entry is disguised as a filtering process, allowing for partial/ambiguous data rather than blocking the user.

---

## 2. General Architecture & Data Strategy

### Data Sources
1.  **Local "Golden" Database:** The app’s persistent SQL database containing canonical Composers and Works.
2.  **External APIs:**
    * **Wikidata:** Used for validating *Composers* (Identity resolution).
    * **OpenOpus:** Used for validating *Works* (Catalog resolution).
3.  **Cached JSON:** A lightweight, client-side file containing the "Top ~500 Composers" and their most common works for instant autocomplete.

### The "Unverified" Buffer
Data that cannot be matched against an external API is accepted but tagged:
* **`Is_Verified: False`**: The entry exists but hasn't been cross-referenced.
* **`Data_Quality: Ambiguous`**: The entry is incomplete (e.g., missing Opus number).

---

## 3. Detailed Workflow

### Phase 1: Composer Selection
*Goal: Identify the human being definitively.*

**Step 1.1: Instant Search (Local)**
* **UI:** User types in the "Composer" field (e.g., "Tchai").
* **Logic:** The system queries the **Local Cached List**.
    * *Match:* "Pyotr Ilyich Tchaikovsky" appears instantly.
    * *Action:* User selects it. **[Go to Phase 2]**

**Step 1.2: External Validation (The "Did you mean?" Fallback)**
* **Trigger:** User finishes typing a name not in the Local Cache (e.g., "Kuhnau") and hits Enter/Next.
* **Logic:** System queries **Wikidata API**.
* **UI:** A modal or dropdown appears: *"We don't have this composer locally. Did you mean: Johann Kuhnau (German Baroque Composer)?"*
* **Action:**
    * *User Confirms:* System imports metadata (Name, Birth/Death, Wiki ID) into the Local Database immediately. **[Go to Phase 2]**

**Step 1.3: The "New Composer" Creation**
* **Trigger:** Wikidata returns no results, or user rejects all suggestions.
* **UI:** System allows the raw text input to stand.
* **State:** Record is saved with `Source: User_Generated` and `Is_Verified: False`.
* **Visual Cue:** In future searches, this composer appears with a small "Unverified" icon/badge.

---

### Phase 2: Work Selection
*Goal: Identify the specific piece of music, handling the "Naming Chaos" (Nicknames vs. Opus).*

**Step 2.1: Smart Search (Alias Matching)**
* **UI:** User sees a search bar for "Work Title."
* **User Input:** User types loosely (e.g., "Moonlight" or "Sonata 14").
* **Logic:** System searches the **OpenOpus (Local Mirror)** using specific logic:
    * Check *Nicknames* ("Moonlight").
    * Check *Catalog Numbers* ("Op. 27").
    * Check *Titles* ("Sonata 14").
* **Result:** Dropdown shows canonical matches: *"Piano Sonata No. 14 in C# Minor (Moonlight)"*.
* **Action:** User selects the work. **[Go to Phase 3]**

**Step 2.2: The "Lazy Builder" (If Search Fails)**
* **Trigger:** User cannot find the work in the dropdown and clicks "Create New Work."
* **UI:** A structured form appears, but **only "Genre/Title" is required**.
    * *Genre:* [Dropdown: Sonata, Prelude, Etude...] (Required)
    * *Key:* [Dropdown] (Optional)
    * *Number:* [Input] (Optional)
    * *Opus:* [Input] (Optional)

* **Logic (The "Filter" Check):**
    * As the user fills these fields, the system runs a **Live Search** in the background.
    * *Example:* User selects `Genre: Sonata` + `Key: C Minor`.
    * *Feedback:* A notification appears: *"Wait! We found 3 existing works matching 'Sonata in C Minor'. Is it one of these?"*

**Step 2.3: Ambiguous Submission**
* **Trigger:** User ignores the matches or truly has a unique work.
* **Action:** User submits the form with incomplete data (e.g., just "Sonata").
* **State:** The work is saved, but tagged `Data_Quality: Ambiguous`.
* **Impact:** This entry is searchable but visually flagged (e.g., "Beethoven - Sonata (?)") so future users know it needs refinement.

---

### Phase 3: Scope & Movement
*Goal: Define exactly what was tested.*

**Step 3.1: Granularity Selector**
* **UI:** Once the Work is identified, a set of radio buttons/checkboxes appears.
* **Prompt:** *"What part of the work was analyzed?"*
* **Options:**
    1.  **Whole Work**
    2.  **Specific Movement(s):** (Generates a dynamic checkbox list based on the Work's metadata if available, e.g., "I. Adagio", "II. Allegro").
    3.  **Excerpt/Fragment:** (Text field for "Measures 1-50" or "Exposition").

---

## 4. Summary of Data States

| Entry Type | Validation Source | System State | User Trust Level |
| :--- | :--- | :--- | :--- |
| **Gold Standard** | Matched via Local/OpenOpus | `Verified` | High |
| **Wiki-Validated** | Matched via Wikidata (Real-time) | `Verified` | High |
| **Ambiguous** | User Entry (Incomplete fields) | `Ambiguous` | Low (Needs refinement) |
| **Unverified** | User Entry (No external match) | `Unverified` | Caution (Potential vandalism) |
