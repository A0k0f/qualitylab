# Research kit for the Learning Lab

Everything needed to run a classroom study with the Learning Lab. Data collection is **off** unless you configure it, and should only be turned on **after IRB approval**.

| File | What it is |
|---|---|
| [SETUP.md](SETUP.md) | Step-by-step: data store, app settings, testing, running it in class, withdrawal, export |
| [STUDY_DESIGN.md](STUDY_DESIGN.md) | Research questions, design (pre/post plus an optional randomised predict vs. no-predict comparison), measures, analysis plan, power, risks: a starting point for an IRB application and a paper |
| [CONSENT_TEMPLATE.md](CONSENT_TEMPLATE.md) | The consent text students see, as a stand-alone sheet |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Every column and every event the app records, and every derived measure |
| [google_apps_script.gs](google_apps_script.gs) | Receives the data into a Google Sheet you own |
| [secrets.example.toml](secrets.example.toml) | Template for the app's research settings |
| [`scripts/analyze_learning_lab.py`](../../scripts/analyze_learning_lab.py) | Turns exported events into participant tables, item statistics, tests and a short report |

Try the analysis with no data at all:

```bash
python scripts/analyze_learning_lab.py --synthetic 60 --out demo_results/
```

The **Instructor** page of the app shows the same results live (with the instructor password) or a synthetic preview.

## What students see

Students who open the Learning Lab on a deployment with research turned on first see a consent screen. They must confirm they are 18 or older to agree. Students who decline get the same activity and nothing is stored. No names, emails, student IDs or IP addresses are ever collected; participants are identified only by a scrambled code made from three answers only they know.
