# Version Control Strategy

## Workflow
We follow a simplified **Feature Branch** workflow.

1.  **Main Branch:** `main` (Production-ready code).
2.  **Feature Branches:** Create a new branch for every task/ticket.
    *   Format: `type/short-description`
    *   Example: `feat/magic-link-auth`, `fix/year-normalization`, `docs/update-roadmap`

## Commit Messages
We adhere to the **Conventional Commits** specification.

### Format
`<type>: <description>`

### Types
*   **feat:** A new feature
*   **fix:** A bug fix
*   **docs:** Documentation only changes
*   **style:** Changes that do not affect the meaning of the code (white-space, formatting, etc)
*   **refactor:** A code change that neither fixes a bug nor adds a feature
*   **test:** Adding missing tests or correcting existing tests
*   **chore:** Changes to the build process or auxiliary tools and libraries (e.g., .appveyor.yml)

### Example
`feat: implement magic link email sender`
`docs: add version control strategy`
