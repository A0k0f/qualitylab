# Participation record (teaching use)

An optional record of **who used the Learning Lab and what they did**, so the instructor can check participation. It is off by default. When it is on, students type their name before starting and the app sends their activity to a Google Sheet that you own.

This is a teaching record, like an LMS activity log. It is **not research data**:

* It is stored separately from the anonymous research data (different Sheet, different token).
* It holds the student's name and never their anonymous research code or experimental condition. The research data never holds the name.
* Do not use it in a paper. Research data come only from students who consent, through the research kit, after IRB approval.

## Setup (about 10 minutes)

1. **Create the Sheet.** Sign in to your **university** Google account and create a new, empty Google Sheet, e.g. `Learning Lab participation`. Share it with nobody.
2. **Add the script.** In the Sheet choose **Extensions → Apps Script**, delete the sample code, and paste the whole of [`research/google_apps_script.gs`](research/google_apps_script.gs). The same script serves both records; this copy belongs to the participation Sheet only.
3. **Set a token.** In Terminal run `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` and paste the result into the line `const TOKEN = '...'`. Save.
4. **Deploy.** **Deploy → New deployment →** gear icon **→ Web app**. Execute as: **Me**. Who has access: **Anyone**. Click **Deploy**, approve the permissions, and copy the **Web app URL** (it ends in `/exec`).
5. **Add the settings to the app.** On share.streamlit.io open your app's **⋮ → Settings → Secrets** and add, below your `instructor_password` line:

   ```toml
   [teaching]
   enabled = true
   course_code = "POM445-F26"
   webhook_url = "the Web app URL from step 4"
   webhook_token = "the token from step 3"
   detail = "full"
   ```

   Save. The app restarts within a minute.
6. **Test.** Open the Learning Lab in a private window, type a test name, run one experiment, then open the **Instructor dashboard** (📋 Participation). Your test name should appear. Delete the test rows from the Sheet (keep row 1).

## What students see

Before anything else, a short screen: *"Your instructor records who uses the Learning Lab and what they do in it … to see participation. The record is kept by your instructor and is not shared. Your answers in the Learning Lab are not graded."* They type their first and last name and continue. The Learning Lab home shows the name they are signed in under.

Tell students in class, or in the syllabus, that the Learning Lab records participation.

## What you see

**Instructor dashboard → 📋 Participation** (password protected) shows one row per student:

| Column | Meaning |
|---|---|
| student | Name as typed (the same name typed differently shows as two rows) |
| sessions, first seen, last seen, minutes active | When they worked (Eastern time); minutes between first and last action in each visit |
| warm-up check, final check, feedback | Whether they completed them |
| process lab experiments, process lab finished | How many experiments they ran; whether they pressed *Finish* |
| missions finished | How many of the six optional missions they completed |
| notes | How many experiment notes they wrote |

Two downloads: the summary table, and every recorded action. The Google Sheet holds the same raw record.

## How much is recorded

* `detail = "full"`: every action with its content: experiment settings, predictions, results, check answers and notes. Useful for reviewing how a student worked.
* `detail = "summary"`: only what was started and finished, and when. Enough for participation, and nothing more.

**When a research study starts, switch to `detail = "summary"`** (or turn the record off) and mention the participation record in your IRB application. A full named record next to the anonymous research data could otherwise be matched by timing, which would undo the research anonymity.

## Good practice

* Keep the Sheet in your university account and share it with nobody. It contains student names, so treat it like gradebook data.
* Delete the Sheet's rows at the end of the term, or when your department's record-keeping rules say so.
* Turn the record off by setting `enabled = false`.
