# Herbie — The AI Counselor Architecture

## What Herbie Is
Herbie is the AI diagnostic engine for Myarra. Named after Herbie in *The Goal*, 
he is the module that finds the constraint. He does not do math in the LLM. 
The math is done in Python/SQL, and the LLM is only used to translate the math 
and the operator notes into a plain-English narrative.

## The Hardware & Model Constraint
- **Current Hardware (Jetson Nano 8GB):** We will use Qwen 2.5 3B (Q4_K_M). 
  Expect ~6 seconds per response. It fits in memory and proves the concept.
- **Future Hardware (Jetson NX 16GB):** We will upgrade to Qwen 2.5 7B or 14B. 
  Expect ~12-15 seconds, but with much higher nuance and instruction-following.

## The Four Functions of `herbie.py`

### 1. `get_line_summary(conn, line_id, date)`
The math engine. It queries the database for:
- Total actual units (`units_filled`)
- Total scrap units (`scrap_units`)
- Total downtime minutes (`downtime_events`)
- The standard rate (`ideal_rate`)

It calculates the **Capacity Gap**:
- `Lost Capacity = (Total Downtime / 60) * Standard Rate`
- `Gross Production = Good Units + Scrap`
- `Theoretical Capacity = Gross Production + Lost Capacity`
- `Variance = Theoretical Capacity - Target`

It returns a dict of these hard numbers.

### 2. `get_floor_context(conn, line_id, date)`
The context engine. It queries:
- Free-text `notes` from `hourly_runs`
- `symptom` and `resolution` from `maintenance_events`
- Active `experiments` (PDCAs) for that line

It returns a string of combined text, so the LLM can read what actually happened.

### 3. `ask_herbie(line_id, date, question)`
The orchestrator. It calls `get_line_summary` and `get_floor_context`, 
formats the `SYSTEM_PROMPT` with the `PHILOSOPHY.md` constraints, 
and sends the request to the local LLM at `http://127.0.0.1:8080/v1/chat/completions`.

### 4. `narrate_capacity_gap(stats, context, question)`
The fallback. If the LLM is offline or times out, this function uses 
Python string formatting to return a rigid summary of the math so the user 
still gets an answer. No AI required.

## The System Prompt Guidelines
The LLM prompt must enforce the following:
- Be direct. No fluff, no "I hope this helps."
- Do not blame the operator.
- Always mention the Capacity Gap.
- If the data is insufficient to answer, say "I cannot answer that."