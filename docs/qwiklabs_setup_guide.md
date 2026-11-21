# Qwiklabs Classroom Setup Guide (Instructor Manual)

This guide explains how workshop instructors and co-trainers provision Qwiklabs classrooms on `https://explore.qwiklabs.com`, guarantee the latest PyPI releases of `google-adk` and `google-agents-cli` inside Cloud Shell, and operate the two-day **90-Minute Google Cloud ADK 2.0 Architecture Conference Hands-On Workshop**.

---

## 1. Workshop Schedule, Capacity & Lab Access Window

| Item | Configuration |
| :--- | :--- |
| **Day 1 Live Session** | **2026-11-26 (Thu) 16:00 - 17:30 JST** (90 min) |
| **Day 2 Live Session** | **2026-11-27 (Fri) 16:00 - 17:30 JST** (90 min) |
| **Classroom Split & Capacity** | **2 separate Classrooms** (Day 1: **100 seats**, Day 2: **100 seats**; ~60 expected attendees/day + 40-seat buffer/day) |
| **5-Hour Lab Access Window** | **15:30 - 21:00 JST** each day (opens 30 min prior; stays active for 3.5 hours after the 90-minute session so attendees can continue self-paced exercises for 5 hours from session start) |
| **Attendee Enrollment Cutoff** | Bulk CSV email import on **2026-11-24 (Tue)** + live Trainer quick-add during check-in for walk-ins |

---

## 2. Delivery Architecture & Latest Package Guarantee

To deliver a zero-friction workshop without requiring local Python 3.13 setups or personal billing accounts—while still using the **latest PyPI releases of `google-adk` and `google-agents-cli`**—this workshop decouples the cloud project environment from the code and tooling versions:

1. **Google Cloud Project & Cloud Shell (`explore.qwiklabs.com` `starter pack` Template)**:
   - Uses the official `End-to-End Gen AI App Starter Pack` Classroom template solely to provision an isolated temporary Google Cloud project per student (up to a **15-hour** project limit) with Vertex AI and Agent Runtime permissions pre-configured.
   - Instructors keep the lab active for **5 hours** (`16:00 - 21:00 JST`, activated at `15:30 JST`) and click **Deactivate Lab** at `21:00 JST` to clean up unused resources.
2. **Latest `google-adk` & `google-agents-cli` via `uv` in Cloud Shell**:
   - Attendees do **not** rely on pre-baked packages in the base lab image. Instead, they clone this repository in Cloud Shell and install dependencies directly from `https://pypi.org/simple` via `uv sync` and `uvx --refresh`, ensuring everyone runs the latest verified `google-adk` and `google-agents-cli` versions.
3. **Interactive Hands-On Tutorial (`docs/index.html`)**:
   - Hosted via GitHub Pages (`https://n-issei-777.github.io/architecture-conference-2026-adk-handson/`), allowing instant updates to code snippets, architecture diagrams, and CLI flags independent of Qwiklabs catalog cycles.

```text
+-------------------------------------------------------------------+
| Attendee Browser (Incognito Window)                               |
|                                                                   |
|  Tab 1: Workshop Tutorial Guide (GitHub Pages / docs/index.html)  |
|    - Step-by-step instructions (Chapters 0 - 6)                   |
|    - One-click Copy buttons for Cloud Shell commands & prompts    |
|                                                                   |
|  Tab 2: Qwiklabs Classroom + Google Cloud Console & Cloud Shell   |
|    - Temporary Google Cloud Project (Vertex AI ADC enabled)       |
|    - Cloud Shell (Python 3.13 + uv + latest adk & agents-cli)     |
|    - Web Preview (Port 8000) for ADK Web UI (`uv run adk web .`)  |
+-------------------------------------------------------------------+
```

---

## 3. Publishing the Standalone HTML Hands-On Guide (`docs/index.html`)

Before opening the classrooms, publish `docs/index.html` so attendees can access it from a single URL:

### Option A: GitHub Pages (Recommended)
1. Push the repository to GitHub (`https://github.com/n-issei-777/architecture-conference-2026-adk-handson`).
2. Open the repository on GitHub and navigate to **Settings** -> **Pages**.
3. Under **Build and deployment**:
   - **Source**: Select `Deploy from a branch`.
   - **Branch**: Select `main` and folder `/docs`.
4. Click **Save**. Within 1-2 minutes, the interactive Codelab-style guide will be live at:
   `https://n-issei-777.github.io/architecture-conference-2026-adk-handson/`

### Option B: Local Preview (For Instructors & Testing)
```bash
python3.13 -m http.server 8080 --directory docs
```

---

## 4. End-to-End Qwiklabs Classroom Setup Timeline

### Phase 1 (Today / T-5 Days): Capacity Intake & Creating the 2 Classrooms
Because each day is capped at **100 seats** (`<= 100` attendees per Classroom), create **two separate Classrooms** (one for `2026-11-26` and one for `2026-11-27`). Student email addresses are **not** required at Classroom creation time.

1. **Submit Capacity Intake Requests (2× — Day 1 and Day 2)**:
   - Submit one Event Intake Form for **2026-11-26 (100 attendees)** and one for **2026-11-27 (100 attendees)** referencing the `End-to-End Gen AI App Starter Pack` lab (use `NO SFDC` if no opportunity ID applies).
   - Record the two **Capacity Planning IDs** received via automated confirmation email (~30 minutes).
2. **Create Classroom #1 (Day 1: 2026-11-26) and Classroom #2 (Day 2: 2026-11-27)**:
   - Sign in to `https://explore.qwiklabs.com` in an Incognito window with an account holding the **Creator** role.
   - Navigate to **Classrooms** -> **+** (**New Classroom**).
   - In **Tag name**, enter `starter pack`, click **Filter**, and select the **End-to-End Gen AI App Starter Pack** workshop template.
   - Configure Classroom fields:
     - **Classroom Name**:
       - Day 1: `Architecture Conference 2026 (Day 1 - 11/26): ADK 2.0 & Google Cloud Hands-On`
       - Day 2: `Architecture Conference 2026 (Day 2 - 11/27): ADK 2.0 & Google Cloud Hands-On`
     - **Public Classroom**: Unchecked
     - **Virtual Classroom**: Unchecked
     - **Trainers**: Add the lead instructor and up to 3 co-trainers/supporters (co-trainers must also hold Trainer/Creator access on `explore.qwiklabs.com` so they can add walk-in students and add lab time on event day).
     - **Time Zone**: `Asia/Tokyo`
     - **Start Date / End Date**: Set each classroom window to cover the event date (`15:30 - 21:00 JST`, or +/- 1 day buffer with manual deactivation at `21:00 JST`).
     - **Location**: Event city or `Remote`
     - **Lab Access**: `Open`
     - **Tags**: Paste the corresponding **Capacity Planning ID** for that day.
     - **Desired Hotlabs**: `0` (standard GCP project provisioning completes in ~1 minute).
   - Click **Create Classroom**.
3. **Configure Subdomain Filter (Critical)**:
   - On the Classroom management review screen immediately after creation, locate **Subdomain Filters**.
   - Select `*` (asterisk) and click **Add Subdomains**, then click **Done**. Without `*`, external attendee email domains cannot access the Classroom.

### Phase 2 (2026-11-24 / T-2 Days): Bulk Attendee Email Enrollment
Classrooms on `explore.qwiklabs.com` display labs **only to individual email addresses listed in the `Students` tab** (wildcard email domains are not supported).

1. Open Classroom #1 (`11/26`) -> **Students** tab, paste the Day 1 attendee email addresses (one per line) or upload the CSV, and click **Add Student**.
2. Repeat for Classroom #2 (`11/27`) with the Day 2 attendee email list.
3. Share pre-event instructions with registered attendees if possible:
   - Ask attendees to sign up at `https://explore.qwiklabs.com` using the **exact same email address** they registered with for the conference (they can also complete sign-up at the beginning of the session).

### Phase 3 (T-24 Hours): Pre-Flight Instructor Verification Checklist
Verify the full flow in an **Incognito Window** before Day 1:

- [ ] **Activate & Test Lab Launch**: Temporarily click **Activate Lab** -> **Open Lab** -> **Start Lab**, copy `Username`, `Password`, and `Project ID`, and sign in to Google Cloud Console in an Incognito window.
- [ ] **Verify Cloud Shell & ADC Credentials**:
  ```bash
  gcloud config set project YOUR_QWIKLABS_PROJECT_ID
  export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
  export GOOGLE_CLOUD_LOCATION=global
  export GOOGLE_GENAI_USE_VERTEXAI=TRUE
  gcloud auth list
  ```
- [ ] **Verify Repository Clone, Python 3.13 + `uv`, and Latest PyPI Packages (`google-adk 2.15.0` / `google-agents-cli 1.15.0`)**:
  ```bash
  git clone https://github.com/n-issei-777/architecture-conference-2026-adk-handson.git
  cd architecture-conference-2026-adk-handson
  uv sync --dev --index https://pypi.org/simple --python python3.13
  uv run adk --version
  uv run agents-cli --version
  ```
- [ ] **Verify Automated Tests & Static Checks Pass**:
  ```bash
  uv run pytest
  uv run ruff check .
  uv run ty check
  ```
- [ ] **Verify ADK Web UI via Cloud Shell Web Preview**:
  ```bash
  uv run adk web . --port 8000
  ```
  Open Cloud Shell **Web Preview** -> **Preview on port 8000** and confirm both `step1_basic_agent` and `step2_workflow_agent` load in the dropdown.

---

## 5. Day-of-Workshop Runbook (2026-11-26 & 2026-11-27, JST)

| Time (JST) | Phase / Chapter | Instructor & Co-Trainer Actions |
| :--- | :--- | :--- |
| **15:30 - 16:00** | **Pre-Session Prep** | Open the day's Classroom on `https://explore.qwiklabs.com` and click **Activate Lab** (do **not** click Deactivate during the event). Keep the **Students** tab open so co-trainers can immediately add any walk-in or alternate email addresses. |
| **16:00 - 16:05** | **Chapter 0: Overview & Architecture** | Share `https://explore.qwiklabs.com` (or direct `https://explore.qwiklabs.com/classroom/<ID>/`) and the HTML Tutorial URL (`https://n-issei-777.github.io/architecture-conference-2026-adk-handson/`). Frame the core thesis: why deterministic `before_tool_callback` + ADK 2.0 `Workflow` are required for production. |
| **16:05 - 16:15** | **Chapter 1: Environment Setup** | Have attendees open an **Incognito Window**, sign in to `explore.qwiklabs.com` (purple Classroom card on home page), click **Start Lab**, open Cloud Shell, clone the repository, and run `uv sync --dev --index https://pypi.org/simple --python python3.13`. Co-trainers add any unmatched attendee emails in **Students** -> **Add Student**. |
| **16:15 - 16:35** | **Chapter 2: Step 1 — Core ADK & Guardrails** | Have attendees read `step1_basic_agent/agent.py` and `src/workcation_concierge/guardrails.py` before running `adk web`. Test Sapporo 2-night booking (Approved) vs. Suite / Hawaii over-budget booking (Blocked 100% by `enforce_booking_guardrail`). |
| **16:35 - 17:05** | **Chapter 3: Step 2 — ADK 2.0 `Workflow` & `agy`** | Run `uv run agents-cli setup` to equip `agy` with official ADK skills. Walk through the 6-node hybrid graph (`mode="task"` on `gemini-4-neon`, parallel 0-LLM Python function + `gemini-4-hydrogen`, `JoinNode`, deterministic `if` router, and `RequestInput` HITL gate). Test both Route A (Sapporo) and Route B (Hawaii -> `RequestInput` approval -> `Session.state["approved_limit_jpy"]` update). |
| **17:05 - 17:25** | **Chapter 4: Step 3 — Evaluation & Deployment** | Run `uv run pytest`, `uv run ruff check .`, `uv run ty check`, and `uv run agents-cli eval run`. Walk through deploying to **Vertex AI Agent Runtime (Agent Engine)** via `uv run agents-cli deploy --deployment-target agent_runtime`. |
| **17:25 - 17:30** | **Chapters 5 & 6: Gemini Enterprise & Wrap-Up** | Introduce one-command publishing (`uv run agents-cli publish gemini`) and summarize why developer CLI harnesses (`agy`, etc.) build the agent while ADK 2.0 governs runtime execution. Announce that the Qwiklabs environment remains open until **21:00 JST** for self-paced practice. |
| **17:30 - 21:00** | **Post-Session Self-Paced Window** | Leave the Classroom lab **Active** so attendees have a full **5 hours** from session start (`16:00 - 21:00 JST`) to experiment on their own. |
| **21:00** | **Lab Shutdown** | Open the Classroom on `explore.qwiklabs.com` and click **Deactivate Lab** to shut down remaining lab environments and conserve cloud resources. |

---

## 6. Common Attendee Troubleshooting FAQ

### Q1: Attendee signs in to `explore.qwiklabs.com` and does not see the purple Classroom card
- **Cause**: Either (a) the attendee signed in with a different email address than the one registered on `2026-11-24`, (b) the lab has not been activated yet, or (c) `*` is missing from **Subdomain Filters**.
- **Fix**: Ask the attendee which email address they signed in with, add that exact email under **Students** -> **Add Student**, and ask them to refresh `https://explore.qwiklabs.com`.

### Q2: Cloud Shell fails to load or stays stuck on "Connecting..."
- **Cause**: Third-party cookies are blocked in the Incognito window.
- **Fix**: Allow third-party cookies for `console.cloud.google.com` in the browser address bar, or click Cloud Shell's **Open in new window** button.

### Q3: `DefaultCredentialsError` when running `adk web` or `pytest`
- **Cause**: `GOOGLE_CLOUD_PROJECT` or `GOOGLE_GENAI_USE_VERTEXAI=TRUE` is not set in the current terminal tab.
- **Fix**: Copy `.env_example` to `.env` with the Qwiklabs project ID, or run:
  ```bash
  export GOOGLE_GENAI_USE_VERTEXAI=TRUE
  export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
  export GOOGLE_CLOUD_LOCATION=global
  ```

### Q4: Port 8000 is already in use when switching from Step 1 to Step 2
- **Cause**: A previous `uv run adk web .` server is still running in another terminal tab.
- **Fix**: Running `uv run adk web .` from the repository root already exposes **both** `step1_basic_agent` and `step2_workflow_agent` in the top-left dropdown without restarting. If restarting is needed, press `Ctrl+C` in the running terminal tab or pass `--port 8080`.
