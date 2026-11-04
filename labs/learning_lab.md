# Learning Lab: teaching guide

The **Learning Lab** (in the app under *For students*) lets senior business students learn quality management by experimenting. Students need only a browser. No statistics software, no coding, no prior SPC.

Its centre is the **Process Lab**. Each student sets up a process of their own, decides what goes wrong and when, chooses how to watch it, predicts what will happen and runs the experiment. Every number and chart is generated from the student's settings, so there is no fixed scenario to copy and no single right answer: students build their understanding by testing their own ideas. Six short guided missions are available as optional extras.

It is designed to come *before* or *alongside* Labs 1–4. The Lab builds intuition about variation, monitoring and the cost of quality; the labs then build technical skill on the SPC Toolkit and Decision Studio.

## The Process Lab

| Students set | Choices |
|---|---|
| **The process** | What is measured and its unit; target; lower and/or upper specification limit; unit-to-unit variation (σ); where the process is actually centred; units per sample (1–25); number of samples; baseline length; volume and costs |
| **What goes wrong** | Any number of changes, each starting at a sample they choose: sudden shift in the average, gradual drift, more variation, a one-off outlier; or nothing (a control run) |
| **How it is watched** | Shewhart chart (I-MR, X̄-R or X̄-S, chosen from the sample size), EWMA or CUSUM; signal rules (limits only, Western Electric, all Nelson rules); limits estimated from a baseline or known; whether people react to signals; EWMA λ and L, CUSUM k and h |
| **Before each run** | A goal (or their own question), and a prediction: will the chart catch the change, after how many samples, how many false alarms, what share out of spec, why, and how confident |

After each run students see what really happened (every unit, the true average and spread) next to what the chart saw (limits, signals, fixes), their prediction against the outcome, a plain-language reading, and the cost. They can re-run the same design with new random data, run it **200 times** to see the typical result, change one thing and run again, keep a note, and download all their experiments as a CSV.

### Questions to give students

Open questions work best: they leave the design of the experiment to the student.

1. How small a shift can your chart catch within 10 samples? What would you change to catch a smaller one, and what does it cost?
2. Does adding run rules help? Measure both sides: speed of detection and false alarms. (Use *Run it 200 times*.)
3. A colleague says EWMA is always better than a Shewhart chart. Design experiments that show when that is true and when it is not (try an outlier, or more variation).
4. Put a change inside the baseline period. What happens to the limits, and why does it matter for how a company sets up a chart?
5. Make your process capable but badly monitored, and then poorly capable but perfectly monitored. Which ships more defects? What does that say about inspection versus capability?
6. Find the cheapest way to watch your own process. Which costs drive the answer?
7. Run the same design twice. Why are the results different, and how many runs would you trust?

### Ways to run it

**One 75-minute class.** Warm-up check (6 min) → a 5-minute demo of one experiment on the projector → Process Lab with two or three of the questions above (40 min) → class debrief with the Instructor page (10 min) → final check (6 min).

**Assignment.** Students answer one question with at least four experiments, attach their experiments CSV, and write a one-page memo to a manager: what they tested, what they found, what they recommend.

**Spread over the term.** Return to the Process Lab whenever a topic is introduced (variation and Deming, control charts, run rules, capability, cost of quality, monitoring design).

## The six guided missions (optional)

| Mission | Course objective | What students do | The idea they should leave with |
|---|---|---|---|
| 🔴 **The Red Bead Factory** (~12 min) | TQM philosophy; Deming | Manage six workers scooping beads. Reward, warn or fire them for three days, then pick one change to the system | Most variation comes from the system, which management owns. Rewarding and punishing people for random variation teaches nothing and the "improvement" that follows is regression to the mean |
| 📡 **Signal or Noise?** (~15 min) | SPC; problem-solving | Sixteen control charts from eight businesses. Investigate ($300) or leave alone (missing a real problem costs $2,000). Two rounds, with the Western Electric rules taught in between | Patterns, not single unusual points, separate special from common causes. Both kinds of mistake cost money. Their score (d′) shows whether they improved |
| 🎯 **The Tampering Trap** (~10 min) | Deming; SPC | Run a filling machine by hand for 15 bottles, then compare the four funnel rules | Adjusting a stable process after every measurement makes it worse (about 41 % more spread for one correction per unit) |
| 📏 **Keep the Customer** (~12 min) | SPC; capability; decision-making | Predict out-of-spec rate; sort four processes as in control or not and capable or not; find the cheapest way to Cpk ≥ 1.33 | Control limits describe the process; specification limits describe the customer. Centering is often cheaper than new equipment. Inspection sorts but doesn't improve capability |
| 💰 **Where Does the Money Go?** (~12 min) | Quality as competitive strategy; cost of quality | Classify costs as prevention, appraisal, internal or external failure; read a Pareto chart; spend a $40,000 budget across six projects | Rank problems by cost, not by count. The best portfolio is not the one a simple rule of thumb picks |
| 🧭 **Be the Quality Manager** (~10 min) | Decision-making for quality improvement | Design an inspection plan for a bottling line and see its cost over a simulated year; try again | Checking is an investment with a cost and a return. A small sample on a control chart, taken often, beats the "check and react to spec" habit |

Plus a **12-question concept check** at the start and the end (same questions, different order; answers and explanations are shown only after the final check) and a 3-minute feedback survey.

### Using the missions

**As a class opener.** Red Beads and Signal or Noise take about 30 minutes together and work well before the first Process Lab session.

**Spread over the term.** Each mission on the day its topic is introduced (Red Beads with Deming, Signal or Noise with control charts, the funnel with process variation, Keep the Customer with capability, Where Does the Money Go with cost of quality, Be the Quality Manager near the end). Final check in the last week.

**Homework before a lecture.** Students do the mission before class; the lecture starts from their results (see below).

## Debrief with the class's own results

The **Instructor** page (under *For analysts & classes*) shows class-level, anonymous results: for the Process Lab, how many experiments students ran, which settings they changed, how often they changed one thing at a time, and whether their predictions improved from one experiment to the next; for each mission, e.g. how many students warned the worker with the most red beads, how many investigated the "tempting" noise charts, how much their own adjusting widened the spread in the funnel game. Showing the class its own numbers is the most effective debrief.

The whole page is locked with a password that only the app owner sets (`instructor_password` in the app's Secrets; see [docs/research/SETUP.md](../docs/research/SETUP.md)). Class results need research collection turned on; before that, the unlocked page offers a synthetic preview.

Good debrief questions:

1. *Red beads:* "Most of you warned or replaced the worker with the most red beads on Day 1. What happened to that worker on Day 2? Why?"
2. *Signal or Noise:* "Which chart fooled the most people? What would you look for next time?"
3. *Funnel:* "Where in your own job or life do people adjust after every result?" (sales targets, diets, thermostats, investment portfolios)
4. *Capability:* "Your plant has a control chart showing no signals for six months. The customer is still unhappy. How?"
5. *Pareto:* "The complaint that happens most is not the one that costs most. What does this mean for how your company tracks quality?"
6. *Manager:* "Why do many companies still inspect at the end of the line instead of monitoring the process?"

## Graded follow-up (optional)

Students can download their **learning record** (an HTML page with their own predictions, decisions and reflections) from the Learning Lab. A short assignment:

> In one page, describe one prediction you got wrong in the Learning Lab, why you made it, and what it would cost a real company to make the same mistake. Use one concept from the textbook to explain it.

Grade the reflection, not the scores in the missions, so that students are free to experiment and make mistakes. Grading must not depend on whether a student takes part in the research study.

## Checking participation

To see who used the Learning Lab and what they did, turn on the optional participation record: students type a participation code you give them and their activity goes to a Google Sheet you own. It is kept apart from research data. See [docs/PARTICIPATION.md](../docs/PARTICIPATION.md).

## Research use

If you want to study how much students learn, the Learning Lab can store anonymous responses from students who consent. It is **off by default**. See [docs/research/](../docs/research/) for the IRB-ready study design, consent text, setup steps and analysis script.
