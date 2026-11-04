# Turning on research data collection

The Learning Lab works for everyone with **no setup and no data collection**. Research collection is an extra layer that stays switched off until you configure it, and it should only be switched on **after your IRB has approved the study**.

When it is on, each student first sees a consent screen. Students who agree (and confirm they are 18 or older) create an anonymous code; their answers, predictions and decisions are then stored without names. Students who decline get exactly the same Learning Lab and nothing they do is stored.

## Checklist

| | Step | Where |
|---|---|---|
| ☐ | IRB approval (exempt or expedited review is typical for this design) | [STUDY_DESIGN.md](STUDY_DESIGN.md), [CONSENT_TEMPLATE.md](CONSENT_TEMPLATE.md) |
| ☐ | Create the Google Sheet that receives the data | Step 1 below |
| ☐ | Add the research secrets to the app | Step 2 below |
| ☐ | Test with a dummy participant, then delete the test rows | Step 3 below |
| ☐ | Share the link with students and walk through the consent screen in class | Step 4 below |
| ☐ | Export and analyse after final grades are submitted | Step 5 below |

## Step 1 · Create the data store (Google Sheet, about 10 minutes)

Use the storage platform your IRB approved. Most universities approve their own Google Workspace or Microsoft 365 accounts for de-identified data. The instructions below use Google; a Microsoft Power Automate flow that accepts the same JSON works too (see the end of this page).

1. Sign in to your **university** Google account and create a new, empty Google Sheet. Name it something like `Learning Lab study data`. Do not share it with anyone who is not on the IRB protocol.
2. In the sheet choose **Extensions → Apps Script**. Delete the sample code and paste the whole of [`google_apps_script.gs`](google_apps_script.gs).
3. Make a random token. In Terminal (Mac) run:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Paste the result between the quotes on the line `const TOKEN = '...'` and save (💾).
4. Choose **Deploy → New deployment**. Click the gear next to *Select type* and pick **Web app**.
   * Execute as: **Me**
   * Who has access: **Anyone** (the token, not the URL, is what protects the data; this setting only lets the app reach the script)
5. Click **Deploy**, approve the permissions Google asks for, and copy the **Web app URL**. It ends in `/exec`.

The sheet gets a tab called `events` the first time data arrive. One row is one event (an answer, a decision, a prediction...). Columns are described in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

> If you later edit the script, choose **Deploy → Manage deployments → Edit → Version: New version**. Creating a *new* deployment instead gives a new URL, and the app would keep sending to the old one.

## Step 2 · Add the research settings to the app

Open the app on [share.streamlit.io](https://share.streamlit.io), click **⋮ → Settings → Secrets**, and paste the block from [`secrets.example.toml`](secrets.example.toml), filled in:

```toml
instructor_password = "a password you choose"

[research]
enabled = true
study_title = "Learning quality management with interactive simulations"
irb_protocol = "the number on your approval letter"
institution = "University of Massachusetts Dartmouth"
pi_name = "Your name"
pi_email = "you@umassd.edu"
irb_contact = "the UMassD IRB office (add the contact your approval letter gives)"
course_code = "POM445-SP27-01"
backend = "webhook"
webhook_url = "the Web app URL from step 1"
webhook_token = "the same token you put in the Apps Script"
salt = "another random string from the command above"
conditions = ["predict", "no_predict"]
```

Save. The app restarts within a minute.

What each setting does:

| Setting | Purpose |
|---|---|
| `enabled` | Master switch. `false` (or no `[research]` block at all) means nothing is ever collected. |
| `irb_protocol`, `pi_name`, `pi_email` | Required. Shown on the consent screen. Collection refuses to start if any is missing. |
| `irb_contact` | Optional line telling students whom to contact about their rights as participants. |
| `course_code` | Stamped on every row so several sections or semesters can share one sheet. Change it each term. |
| `salt` | Secret used to scramble the anonymous codes. **Never change it during a study**: the same student would get a different code and pre/post answers would no longer link. Never share it. |
| `conditions` | Optional experiment. Each participant is assigned to one condition by their code, so they keep it across sessions. `no_predict` hides the "predict first" steps. Remove the line for a single-group study. |
| `instructor_password` | Top-level line, above `[research]`. Locks the whole **Instructor** page; without it the page stays locked for everyone. |
| `data_access_note` | Optional. Replaces the default sentence on the consent screen about who sees the data and when. It must match your approved protocol. |

The Instructor page has a **Configuration** box that lists anything missing. If a required setting is wrong, collection stays off and the app keeps working normally.

Secrets live only in Streamlit Cloud. They are never in the GitHub repository, and `.gitignore` excludes `.streamlit/secrets.toml` in case you also test on your own computer.

## Step 3 · Test before students see it

1. Open the app in a private browser window, go to **Learning Lab**, agree, and create a code with made-up answers (for example `ZZ`, `01`, `ZZ`).
2. Do the warm-up check and one mission.
3. Within a few seconds rows appear in the `events` tab. The **Instructor** page (with the password) should show one participant.
4. Delete the test rows from the sheet (keep row 1, the header).

## Step 4 · In class

* Show the consent screen on the projector and read the key points aloud: voluntary, anonymous, no effect on grades, same activity either way.
* Ideally someone other than the instructor of record introduces the study, or the instructor leaves the room while students decide. Ask your IRB what it expects.
* Ask students to write down the code shown on the home screen if they want to withdraw later.
* The full Learning Lab takes about 75 to 90 minutes: one long class, or the warm-up check plus three missions in one class and the rest in the next. Progress on screen lives in the browser tab, so students should finish a mission before closing it. When they come back, they agree again and re-enter the **same three answers**; that gives them the same code, so the analysis links both sessions (it uses each student's first warm-up check and last final check). Tell students to skip the warm-up check on day two.

**Withdrawal.** A student who wants their data removed emails the PI their code (it looks like `P-3F9A0C12BD`). Delete every row with that `participant_id` from the sheet.

## Step 5 · Export and analyse

* **Instructor page → Data & export** downloads the raw events (CSV) and a participant-level workbook (Excel).
* Or run the analysis script on an exported CSV:
  ```bash
  python scripts/analyze_learning_lab.py events.csv --out results/
  ```
  It writes `participants.csv` (one row per student, all measures), `items.csv` (each concept-check question, pre vs. post), `summary.json` (paired tests, effect sizes, condition comparison) and a short `report.md`.
* Try the whole pipeline now, with no students, on synthetic data:
  ```bash
  python scripts/analyze_learning_lab.py --synthetic 60 --out demo_results/
  ```

Keep exported files on university storage approved by your IRB. Do not commit them to GitHub (`.gitignore` already excludes `research_data/` and `*.jsonl`).

## Running the app on your own computer instead

Put the same `[research]` block in `.streamlit/secrets.toml` inside the project folder, with `backend = "local"` and `local_path = "research_data/events.jsonl"`. Every event is appended to that file. This is useful for a lab session on one machine or for testing.

## Using Microsoft 365 instead of Google

Any HTTPS endpoint that behaves like the Apps Script works:

* `POST` with body `{"token": "...", "events": [ {...}, {...} ]}` appends the events and answers `{"ok": true}`. A wrong token answers `{"ok": false}`.
* `GET ?token=...&action=export` answers `{"ok": true, "events": [ ... ]}`.

In Power Automate this is an *instant cloud flow* with the trigger "When an HTTP request is received", a condition on the token, and "Add a row into a table" for each event (Excel Online on OneDrive or SharePoint). The export can be skipped: download the Excel file directly and run the analysis script on it saved as CSV.

## How the privacy protections work

* **No identifiers.** The app never asks for or stores names, emails, student IDs or IP addresses.
* **Self-generated code.** Three answers only the student knows (two letters of a parent's first name, birth day, two letters of their birth town) are combined with the secret salt and hashed with SHA-256. Only the first 10 hex characters are kept (`P-...`). Neither the researcher nor anyone with the sheet can reverse it. The salt prevents someone from trying all possible answers.
* **Consent first.** No event is sent before the student agrees and confirms they are 18 or older. Declining stores nothing.
* **Free text.** Text boxes remind students not to include names. Screen open-text answers before sharing any quotes.
* **Students keep their own record.** Everyone, participant or not, can download their own learning record from the app.
