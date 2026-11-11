# Herbie — The AI Counselor Architecture

## Product Philosophy
Herbie is not a summarizer. Herbie is a router and a coach. The core problem Myarra solves is the "Check" step of PDCA. Herbie is the missing feedback loop. He must never guess, never hallucinate, and never summarize a standard into a lie.

## The Hardware Tier Split
To make this commercially viable, we are building a two-tier product:
- **The Nano (Base Model):** Runs Qwen 2.5 3B. Handles single-turn queries, point lookups, and strict template-based narratives. Fast enough (~6 seconds) to feel responsive. No multi-turn conversation memory.
- **The NX (Premium Model):** Runs Qwen 2.5 7B or 14B. Handles multi-turn conversation state, proactive coaching ("You have 17 unaccounted minutes, go find them"), and complex root-cause analysis. This is the upsell.

## The Three-Layer Architecture

### Layer 1: The Classifier (The Router)
When a user asks a question (either via Web UI or Telegram starting with "Hey Herbie"), the LLM classifies the query into one of five types:
1.  **Job Lookup:** "What was the FTQ for WO-2611-004?"
2.  **Attribution:** "Why did we lose time on that job?"
3.  **Reconciliation:** "How many minutes are unaccounted for?"
4.  **Aggregation (Threshold):** "Which jobs had more than 30 minutes of downtime?"
5.  **Aggregation (Time Window):** "What is our unaccounted downtime for the last 30 days?"

### Layer 2: The Function Library (Hard Math)
The classifier triggers a deterministic Python function. The LLM is *never* allowed to do math or write raw SQL that aggregates data. It only calls these functions:
-   `get_job_summary(job_number)`
-   `get_downtime_attribution(job_number)`
-   `get_unaccounted_minutes(filters)`
-   `get_jobs_with_downtime_over(threshold, days)`
-   `get_line_summary(line_id, date)`

### Layer 3: The Narrator (The Voice)
The LLM receives the exact dictionary of numbers from Layer 2 and writes the response. 
**Strict Rule:** If the LLM references a number, it must be in the dictionary. If it quotes an operator note, it must quote it *verbatim*. No summarizing. No characterizing.

## The New Metric: Unaccounted Minutes
The core metric that drives Herbie's proactive coaching is the gap between expected output and explained downtime.

We will create a new SQL view: `v_unaccounted_minutes_by_run`.
**Formula:**
-   `Expected Units = (duration_min * ideal_rate) / 60`
-   `Gap Units = Expected Units - units_filled`
-   `Gap Minutes = (Gap Units / ideal_rate) * 60`
-   `Unaccounted Minutes = Gap Minutes - recorded_downtime_minutes` (Floor at 0).

If `Unaccounted Minutes > 0`, the operator failed to log a reason for the loss. This is the glaring hole.

## The Interface
-   **Web UI:** A dedicated `/herbie` page. A chat-like interface.
-   **Telegram:** The bot listens for "Hey Herbie" and routes to the counselor logic. Otherwise, it behaves as the standard floor data capture bot.

## The Proactive Loop (NX Only)
On the NX, Herbie doesn't just wait for questions. At the end of a shift, he reviews the data. If he finds a job with >15 minutes of unaccounted time, he sends a Telegram message to the plant manager: *"Line 3 had 22 minutes of unaccounted downtime on WO-2611-004 today. You might want to talk to the line lead. The operator notes say 'minor filler jam'. That doesn't explain the 22 minutes."*