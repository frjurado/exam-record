# Phase 2.1: Importer Services Implementation Plan

## Goal
Implement the core data loop services to fetch and verify Composers (Wikidata) and Works (OpenOpus).

## User Review Required
- **Caching Strategy**: 
  - **Composers**: We will fetch the "Popular/Essential" list from OpenOpus to seed our database. This allows for fast, local Level 1 autocomplete. Wikidata will be used as a Level 2 fallback for composers not in this initial list (long tail).
  - **Works**: We will query OpenOpus dynamically for work validation/alias matching.

## Proposed Changes

### [app]
#### [NEW] [app/services/__init__.py](file:///f:/Antigravity/exam-record/app/services/__init__.py)
- Empty init file.

#### [NEW] [app/services/wikidata.py](file:///f:/Antigravity/exam-record/app/services/wikidata.py)
- `search_composer(query: str) -> List[Dict]`
  - Queries Wikidata API for composers matching the name.
  - Returns simplified objects: name, wikidata_id, birth/death, description.
  - **Fallback**: Used when a composer is not found in the local DB (populated from OpenOpus).
- `get_composer_by_id(wikidata_id: str) -> Dict`
  - Fetches details for a specific ID.

#### [NEW] [app/services/openopus.py](file:///f:/Antigravity/exam-record/app/services/openopus.py)
- `get_popular_composers() -> List[Dict]`
  - Fetches the list of popular/essential composers from OpenOpus to seed the database.
- `search_work(query: str, composer_id: str = None) -> List[Dict]`
  - Queries OpenOpus for works.
  - Strategy: Search works by title/keyword. OpenOpus API allows `work/search/:search_term/:composer_id` (optional).

### [tests]
#### [NEW] [tests/services/test_wikidata.py](file:///f:/Antigravity/exam-record/tests/services/test_wikidata.py)
- Test searching for "Beethoven".
- Mock `httpx` responses.

#### [NEW] [tests/services/test_openopus.py](file:///f:/Antigravity/exam-record/tests/services/test_openopus.py)
- Test searching for "Moonlight Sonata".
- Mock `httpx` responses.

## Verification Plan

### Automated Tests
- Run `pytest tests/services/` to verify the service logic and parsing.

### Manual Verification
- We can create a temporary script or use `fastapi shell` (if configured) or just a python script to call these services and print results to verify they talk to the real APIs correctly (before mocking or for integration testing).
