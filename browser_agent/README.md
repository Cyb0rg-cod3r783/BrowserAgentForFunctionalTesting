# 🤖 Browser Agent — AI-Powered Functional Testing

Browser Agent replaces manual Selenium test scripting with a two-phase AI-powered workflow. Instead of writing brittle selectors and hard-coded test scripts, you simply **record** yourself using the app and the agent does the rest.

When your web application changes — new fields, renamed buttons, restructured flows — you just re-record. The agent regenerates all test cases automatically. No manual test script editing. Ever.

---

## Prerequisites

- **Python 3.11+**
- **Chromium** (installed automatically via `playwright install chromium`)
- **Groq API key** — free at [console.groq.com](https://console.groq.com)

---

## Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd browser_agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install chromium

# 4. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

---

## Usage

### `learn` — Record a session and generate test cases

```bash
python agent.py learn --app myapp --url https://example.com/login
```

Opens a visible browser. Use the app normally (fill forms, click buttons, navigate). Press **Ctrl+C** when done.

The agent will:
1. Analyze your recorded interactions with an LLM
2. Build a structured model of your app (pages, elements, flows)
3. Generate test cases: 1 happy path + 3-5 negative + 2-3 edge cases per flow

### `test` — Execute all test cases

```bash
# Run all tests headlessly (CI mode)
python agent.py test --app myapp

# Run with visible browser (debugging)
python agent.py test --app myapp --no-headless

# Run only a specific test category
python agent.py test --app myapp --suite negative
```

### `report` — Open the HTML test report

```bash
python agent.py report --app myapp
```

Opens the most recent HTML report in your default browser. Reports include:
- Run summary (total/passed/failed/errored)
- Per-test details with step-by-step results
- Embedded screenshots for each step and failure

### `relearn` — Update model after app changes

```bash
python agent.py relearn --app myapp
```

Records a new session, compares it against the old model, shows a diff table, and asks if you want to activate the new version.

### `diff` — Compare two versions

```bash
python agent.py diff --app myapp --v1 v1_2025-01-01 --v2 v2_2025-01-15
```

Shows a structured diff of pages, elements, and flows between two recorded versions.

### `status` — Show all registered apps

```bash
python agent.py status
```

Shows a table with: App name | Base URL | Active Version | Last Run | Pass Rate

---

## How It Works

**LEARN Phase:**
1. You open a browser and use the app normally
2. A JavaScript listener captures every click, input, and form submission
3. Page navigation events capture the accessibility tree and a screenshot
4. When you stop recording, the raw event log is sent to Groq's LLM
5. The LLM identifies elements (semantic labels, validation rules), understands flows, and generates test cases
6. Everything is stored in a local SQLite database

**TEST Phase:**
1. The agent loads test cases from the database
2. For each test, it launches a Playwright browser and navigates to the start URL
3. It locates elements using a priority chain: `aria-label → placeholder → role → id → css → LLM fallback`
4. It executes actions (fill, click, check, select) and evaluates assertions
5. Screenshots are taken at each step
6. Results are saved and an HTML+JSON report is generated

---

## Known Limitations

These are out of scope for the current version:

- **CAPTCHA** (reCAPTCHA, hCaptcha) — cannot be automated
- **SMS/email OTP** flows in production — requires real account access
- **Cross-origin iframes** (Stripe, Google Maps embeds) — blocked by browser security
- **Canvas/WebGL UI elements** — not accessible via DOM/accessibility tree
- **Mobile browser emulation** — desktop Chromium only

---

## Project Structure

| Path | Description |
|------|-------------|
| `agent.py` | CLI entry point |
| `cli.py` | All Click commands |
| `schema.py` | Pydantic v2 data models |
| `config.py` | Environment configuration |
| `core/recorder.py` | Playwright recording engine |
| `core/model_builder.py` | Converts events → ApplicationModel |
| `core/test_generator.py` | Generates TestCase objects from flows |
| `core/executor.py` | Autonomous test execution |
| `core/verifier.py` | Assertion evaluation |
| `storage/db.py` | SQLite CRUD operations |
| `storage/schema.sql` | Database schema |
| `storage/diff.py` | Version comparison |
| `llm/client.py` | Groq API wrapper |
| `llm/cache.py` | LLM response cache |
| `llm/prompts.py` | All prompt templates |
| `utils/locators.py` | Multi-strategy locator resolution |
| `utils/screenshots.py` | Screenshot capture utilities |
| `reporting/html_reporter.py` | HTML report generation |
| `reporting/json_reporter.py` | JSON report generation |
| `reporting/templates/report.html` | Jinja2 report template |
| `assets/event_capture.js` | Browser-injected event listener |
