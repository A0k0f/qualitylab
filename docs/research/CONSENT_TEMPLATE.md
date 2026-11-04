# Consent information (template)

This is the text the app shows on its consent screen, laid out as a stand-alone information sheet for an IRB application. Text in *[brackets]* comes from the app's research settings. If your IRB changes the wording, tell the developer or edit `consent_view()` in `app/lablib/home.py` so the screen matches the approved version exactly.

---

**Study title:** *[study_title]*
**Researchers:** *[pi_name]* (*[pi_email]*), *[institution]*
**IRB protocol:** *[irb_protocol]*

**What is this study about?**
We are studying how interactive simulations help students learn quality management. If you agree, the answers, predictions and decisions you make in the Learning Lab will be stored without your name and analysed for research.

**Is it voluntary?**
Yes. Taking part or not has no effect on your grade. You get exactly the same Learning Lab either way.

**Is it anonymous?**
Yes. We do not record your name, email, student ID or IP address. You will create a code from three answers only you know. We store a scrambled version of it, which lets us link your answers across sessions but not identify you.

**What is stored?**
Your answers to the concept check and the survey; the experiments you design in the Process Lab (your settings, predictions and results) and your decisions in the missions; how long steps took; and any short written notes.

**What are my choices?**
You can skip any question and stop at any time. *[data_access_note, by default:]* The instructor may show anonymous, class-level summaries in class (for example, "60 % of the class chose the supplier fix"). Nobody will look at individual responses until final grades for the course have been submitted, and nobody can tell from the data who took part.

**How do I withdraw?**
Your code appears at the top of the Learning Lab after you agree. Email it to *[pi_email]* and all of your data will be deleted.

**Are there risks or benefits?**
There are no risks beyond those of a normal class activity. You may learn the course material more deeply. The results may improve how quality management is taught.

**Who do I contact?**
Questions about the study: *[pi_name]*, *[pi_email]*. Questions about your rights as a participant: *[irb_contact]*.

☐ I am 18 years of age or older.

**[ I agree to take part ]**  **[ No thanks: use the Learning Lab without taking part ]**

---

*Notes for the IRB application*

* The Learning Lab is an in-class learning activity. Using it is the same for every student. Only the storage of responses depends on consent.
* Under-18 students cannot select "I agree" (the button is disabled until the age box is ticked). They use the activity with nothing stored.
* Many IRBs waive signed consent for anonymous online studies of minimal risk. The on-screen agreement is the record of consent; the app stores a `consent` event with the anonymous code and no other identifier.
* Participants can download their own record of answers from the app at any time.
