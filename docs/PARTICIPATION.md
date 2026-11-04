# Participation record (teaching use)

An optional record of **who used the Learning Lab and what they did**, so the instructor can check participation. It is off by default. When it is on, students type a **participation code** that you give them (for example `QL-7F3K2`) before starting, and the app sends their activity to a Google Sheet that you own. You can download the Sheet at any time as an Excel file or a CSV.

**No names leave your hands.** The Sheet only ever sees codes. The list that matches codes to names stays with you, for example as an Excel file in your UMassD OneDrive. On the Instructor page you can load that list to see names; it is read in memory for that visit and not saved anywhere. Because of this, a free personal Google account works fine as the store; no university license or IT request is needed.

This is a teaching record, like an LMS activity log, and it is **not research data**:

* It is stored separately from the anonymous research data (different Sheet, different token).
* It never contains the anonymous research code or the experimental condition, and the research data never contain the participation code.
* Do not use it in a paper. Research data come only from students who consent, through the research kit, after IRB approval.

## Setup (about 15 minutes, once per term)

**1. Make the codes.** Open the app's **Instructor dashboard**, enter your password, and stay on **📋 Participation**. Open **Participation codes and roster**, paste your students' names (one per line, e.g. copied from the class roster) and click **Download roster**. Save the file (e.g. `learning_lab_roster.csv`) in your UMassD OneDrive. Each download creates new codes, so download once and keep that file.

**2. Create the Sheet.** Sign in to a Google account (a free personal one is fine, or a new one just for this course) and create a blank spreadsheet at sheets.google.com, e.g. `Learning Lab participation`. Share it with nobody.

**3. Add the script.** In the Sheet choose **Extensions → Apps Script**, delete the sample code, and paste the whole of [`research/google_apps_script.gs`](research/google_apps_script.gs) (open it in TextEdit from your project folder and copy everything).

**4. Set a token.** In Terminal run:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the result into the line `const TOKEN = '...'` (between the quotes) and click save 💾. Keep the token for step 6.

**5. Deploy.** **Deploy → New deployment →** gear icon **→ Web app**. Execute as: **Me**. Who has access: **Anyone** (the token protects the data; this setting only lets the app reach the script). Click **Deploy → Authorize access**, pick the account, and if Google says the app isn't verified click **Advanced → Go to (project name) (unsafe) → Allow**: it is your own script. Copy the **Web app URL** (it ends in `/exec`).

**6. Add the settings to the app.** On share.streamlit.io open your app's **⋮ → Settings → Secrets** and make it look like this (your password line stays at the top):

```toml
instructor_password = "your password"

[teaching]
enabled = true
course_code = "POM445-F26"
webhook_url = "the Web app URL from step 5"
webhook_token = "the token from step 4"
identify = "code"
detail = "full"
```

Save. The app restarts within a minute.

**7. Test.** Open the app in a private window, go to **Learning Lab**, type one of the codes from your roster, open the Process Lab and run one experiment. In the Google Sheet a tab called **events** appears with rows. On the Instructor dashboard (📋 Participation), upload your roster: the code shows with its name and 1 experiment. Then delete the test rows in the Sheet (keep row 1, the headings).

**8. Give students their codes**, for example through your course site or by email, and tell them (in class or in the syllabus) that the Learning Lab records participation by code.

## What students see

Before anything else: *"Your instructor records who uses the Learning Lab and what they do in it … You are identified only by the code your instructor gave you; your name is not stored here. Your answers in the Learning Lab are not graded."* They type their code and continue. The Learning Lab home shows the code they are recorded under. Codes are not case-sensitive.

## What you see

**Instructor dashboard → 📋 Participation** (password protected), one row per code, with the name if you uploaded your roster:

| Column | Meaning |
|---|---|
| student, name | Code as typed; name from your roster |
| sessions, first seen, last seen, minutes active | When they worked (Eastern time); minutes between first and last action in each visit |
| warm-up check, final check, feedback | Whether they completed them |
| process lab experiments, process lab finished | How many experiments they ran; whether they pressed *Finish* |
| missions finished | How many of the six optional missions they completed |
| notes | How many experiment notes they wrote |

Two downloads: the summary table and every recorded action. In the Google Sheet, **File → Download → Microsoft Excel (.xlsx)** gives you the raw record as an Excel file.

## How much is recorded

* `detail = "full"`: every action with its content: experiment settings, predictions, results, check answers and notes.
* `detail = "summary"`: only what was started and finished, and when.

**When a research study starts, switch to `detail = "summary"`** (or turn the record off) and mention the participation record in your IRB application, so that it cannot be used to identify research participants.

## Using names instead of codes

If your university provides an approved store (for example a university Google account), you can set `identify = "name"` and students type their name instead. Do not use names with a personal account.

## Good practice

* Keep the roster file (codes and names) in your university storage, never in the Google account.
* Delete the Sheet's rows at the end of the term.
* Turn the record off with `enabled = false`.
