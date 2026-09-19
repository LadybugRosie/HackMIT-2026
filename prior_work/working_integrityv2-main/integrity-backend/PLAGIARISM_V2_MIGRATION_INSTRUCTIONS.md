# Plagiarism V2 Migration — Detailed Instructions

**Goal:** Use the latest plagiarism engine (v2) everywhere and remove the old v1 code. Do not break anything: one button “Run Plagiarism” should run v2 (including internal/peer plagiarism). All other behavior (teacher dashboard, submission fields) must stay the same. (Note: the composite trust score has been removed from the product — plagiarism is an independent signal.)

---

## 1. Where the “Run Plagiarism” Button Is

- **File:** `src/pages/teacher/GradeSubmission.vue`
- **Location:** Teacher grading view → **“Similarity Report”** tab (or “Plagiarism” tab) → button labeled **“Run Plagiarism Check”** or **“Re-run Plagiarism Check”**.
- **Code:**  
  - Button: around **lines 241–252** (class `btn-run-plagiarism`, `@click="runPlagiarismCheck"`).  
  - Handler: **`runPlagiarismCheck()`** at **lines 899–918**.
- **Current behavior:** The button already calls the **v2** endpoint:
  - `POST /api/plagiarism/check-submission/${submissionId}`
  - Body: `{ check_internal: true, check_scholarly: true, check_web: true }`
- **Action:** No frontend change needed for this button. Ensure the backend route for this URL **only** uses v2 (see below). Do not remove or rename this button; only ensure it keeps using v2 and that any other “run plagiarism” flow (e.g. batch) also uses v2.

---

## 2. Backend: What Must Use V2

- **Router:** `integrity-backend/app/routers/plagiarism_check.py`
  - `POST /api/plagiarism/check-submission/{submission_id}` — must call **only** v2 (`check_plagiarism_v2`). It already does; do not reintroduce v1.
  - `POST /api/plagiarism/batch/{assignment_id}` — must call **only** v2 (`batch_check_v2`). It already does; do not use v1 batch here.
- **Scheduler (critical):** `integrity-backend/app/main.py`
  - **Lines 276–318:** `_batch_similarity_loop()` currently calls **v1** `run_batch_similarity` from `app.services.plagiarism`.
  - **Change:** In this loop, replace the v1 call with the **v2** batch:
    - Import and call `batch_check_v2` from `app.services.plagiarism_v2` instead of `run_batch_similarity` from `app.services.plagiarism`.
    - Keep the same assignment query (`batch_similarity_completed` / `due_date`) and the same `update_one` that sets `batch_similarity_completed: True` and `batch_similarity_at` so existing behavior (e.g. “batch ran”) is unchanged.
  - Do not add a second loop or a second flag unless you need to preserve backward compatibility with already-run v1 batches; otherwise one loop calling v2 is enough.
- **Collections for v2:** In `main.py`, `plagiarism_v2.set_collections(...)` is already called. If the app has a `plagiarism_check_results` (or similar) collection for v2 audit storage, pass it as `plagiarism_results=...` so v2 can write results there. Do not remove or rename existing collections used by the frontend (e.g. `plagiarism_score`, `plagiarism_matches` on submissions).

---

## 3. V2 Engine — What It Uses (Do Not Remove)

The v2 engine lives in **`integrity-backend/app/services/plagiarism_v2.py`**. It must remain the single source of plagiarism logic. It uses:

- **OpenAlex:** `search_openalex()` ~line 541, called from `_search_all_scholarly()` ~line 1009.  
  - Used for every scholarly query.
- **Semantic Scholar:** `search_semantic_scholar()` ~line 598, called from `_search_all_scholarly()` ~line 1010 (via `_s2_staggered`).  
  - Used for every scholarly query (staggered for rate limits).
- **Crossref:** `search_crossref()` ~line 642 for search (first query only ~line 1013), and `enrich_publication()` ~line 1049 for DOI enrichment.  
  - Used for search and for enriching matched works.
- **Web:** `_check_web_sources()` ~line 903 uses `_search_duckduckgo()` and optionally `_search_google_cse()` / `_search_brave()`.  
  - DuckDuckGo is always used when web check is on; Google CSE and Brave only if API keys are set.

So: OpenAlex, Semantic Scholar, Crossref, and web (DuckDuckGo + optional Google/Brave) are all used by v2. Do not remove or bypass these when “run plagiarism” is used.

---

## 4. What “Run Plagiarism” Must Do (V2 Only)

- **Single submission (teacher clicks “Run Plagiarism Check” on one submission):**  
  Already uses v2 via `POST /api/plagiarism/check-submission/{id}` → `check_plagiarism_v2(...)` with `check_internal=True`, `check_scholarly=True`, `check_web=True`. Keep it that way.
- **Internal/peer plagiarism:** v2’s `check_plagiarism_v2` and `batch_check_v2` both support internal (peer) checks when `check_internal=True`. The same button and batch must run v2 with internal checks enabled so peer plagiarism is still detected.
- **Batch (e.g. post-deadline):** The scheduler in `main.py` must run **only** `batch_check_v2(assignment_id)` (and no longer `run_batch_similarity`). That way the one “batch” run is also v2 and includes internal plagiarism.

---

## 5. Removing the Old V1 Code (After V2 Is Wired)

- **Do not remove anything until:**  
  (1) The teacher “Run Plagiarism Check” button is confirmed to use only v2, and  
  (2) The post-deadline batch in `main.py` calls only `batch_check_v2`.
- **Then remove or retire:**
  - **`integrity-backend/app/services/plagiarism.py`** — v1 service (`run_batch_similarity`, `check_plagiarism`, `calculate_plagiarism_score`, etc.). Remove all references to this module from the codebase (e.g. `main.py` and any other imports).
  - Any other code paths that still call v1 (e.g. `run_batch_similarity`, `check_plagiarism` from `plagiarism.py`). Search for `from .services.plagiarism import` or `plagiarism.run_batch_similarity` and delete or replace with v2.
- **Do not remove:**
  - `plagiarism_check.py` router (v2 API).
  - `plagiarism_v2.py` (v2 engine).
  - Frontend components that display `plagiarism_score` / `plagiarism_matches` (e.g. `GradeSubmission.vue`, `PlagiarismViewer.vue`).
  - Any submission fields or API contracts: `plagiarism_score`, `plagiarism_matches`, `plagiarism_v2_checked_at`, etc. must keep the same names and shape so the teacher dashboard does not break.

---

## 6. Summary Checklist

1. **Teacher dashboard:** The only “Run Plagiarism” button is in **`src/pages/teacher/GradeSubmission.vue`** (lines ~241–252, handler ~899–918). It already calls the v2 endpoint; leave it as is and ensure the backend for that endpoint uses only v2.
2. **Backend:**  
   - `POST /api/plagiarism/check-submission/{id}` and `POST /api/plagiarism/batch/{assignment_id}` use only **v2** (`check_plagiarism_v2`, `batch_check_v2`).  
   - In **`main.py`**, `_batch_similarity_loop()` calls **`batch_check_v2`** instead of `run_batch_similarity`.
3. **Internal plagiarism:** v2 is used with `check_internal=True` so peer/internal plagiarism is still run from that one button (and from the batch).
4. **V2 sources (do not remove):** OpenAlex, Semantic Scholar, Crossref, and web (DuckDuckGo + optional Google/Brave) as implemented in **`plagiarism_v2.py`** (see section 3 for line refs).
5. **Remove v1:** After 1–4 are done, remove `plagiarism.py` and all references to it; do not break the submission schema or the teacher dashboard.

---

## 7. File Reference Quick List

| Purpose | File |
|--------|------|
| Teacher “Run Plagiarism Check” button and UI | `src/pages/teacher/GradeSubmission.vue` (button ~241–252, handler ~899–918) |
| V2 API routes (check-submission, batch) | `integrity-backend/app/routers/plagiarism_check.py` |
| Post-deadline batch loop (switch to v2 here) | `integrity-backend/app/main.py` (`_batch_similarity_loop` ~276–318) |
| V2 engine (OpenAlex, S2, Crossref, web) | `integrity-backend/app/services/plagiarism_v2.py` (see section 3 for line numbers) |
| V1 engine (to be removed after migration) | `integrity-backend/app/services/plagiarism.py` |

Do not break anything: same button, same submission fields; only the implementation behind “run plagiarism” (single and batch) must be v2, and v1 code removed afterward.
