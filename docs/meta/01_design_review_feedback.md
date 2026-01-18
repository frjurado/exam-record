# Design Review: Exam Record

## 1. Strengths
*   **Clear Value Proposition**: The "Time Capsule" (Post-exam anxiety) and "Expert Hub" (Teacher efficiency) concepts are excellent hooks for the two main user personas.
*   **Smart Data Entry**: The "Standardization over Creation" philosophy using Wikidata/OpenOpus with a "Lazy Builder" fallback is a robust strategy to maintain data quality without frustrating users.
*   **Innovative Validation**: The Traffic Light / Consensus model is a great fit for this domain, avoiding the bottleneck of central moderation.
*   **Low Friction**: Passwordless entry (Magic Links) is crucial for transient student users.

## 2. Flaws & Risks
*   **The "Cold Start" Incentive Cliff**: The consensus model requires volume ($\ge$ 2 votes). Early users will see a lot of "Gray/Neutral" states, which might feel like "Empty/Untrusted" data, discouraging further use.
*   **Normalization Complexity**: The system assumes "Event" uniqueness (Year + Region + Discipline), but in reality, naming conventions for simple things like "Region" or "Institution" can be messy (e.g., "Madrid" vs. "RCSMM"). 
*   **Teacher Verification**: "Steward" status seems to be reputation-gated but initially self-declared. A bad actor could game this to inject bias. Requires a "Report User" flow.

## 3. Doubts & Questions
*   **Privacy**: Are user contributions (exam reports) anonymous to the public? If I share "I got asked Beethoven", is my name attached?
*   **Moderation**: Is there a manual "Panic Button" or moderation queue for obviously malicious data (spam, vandalism) beyond the consensus disputes?
*   **Initial Seeding**: Is there a plan to seed the database with historic data? An empty database is the biggest risk to the "Search" value proposition.

## 4. Non-Technical Design Decisions Needed
Before technical specs, we need to define the controlled vocabularies:
1.  **Region/Institution Strategy**: Do we support *Countries > Cities > Conservatories*? Or just generic *Regions*? We need a fixed list or a strategy to canonicalize these.
2.  **Discipline Taxonomy**: Is it a fixed list (Piano, Violin, Cello)? Or open? (Recommendation: Fixed list to ensure "Event" matches work).
3.  **Academic Year Format**: How do we handle "2023-2024"? Is it "2023" (Start year) or a string? (Recommendation: Normalized "Academic Year Start" integer).
