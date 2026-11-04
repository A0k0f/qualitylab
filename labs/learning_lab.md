# Learning Lab: teaching guide

The **Learning Lab** (in the app under *For students*) is a set of six short missions for senior business students. Each one puts the student in a manager's seat: they **predict** what will happen, **decide**, see the **consequences**, and **explain** them. Students need only a browser. No statistics software, no coding, no prior SPC.

It is designed to come *before* or *alongside* Labs 1–4. The missions build the intuition (why not blame the worker, why not adjust after every unit, why a stable process can still fail the customer); the labs then build the technical skill on the SPC Toolkit and Decision Studio.

## The six missions

| Mission | Course objective | What students do | The idea they should leave with |
|---|---|---|---|
| 🔴 **The Red Bead Factory** (~12 min) | TQM philosophy; Deming | Manage six workers scooping beads. Reward, warn or fire them for three days, then pick one change to the system | Most variation comes from the system, which management owns. Rewarding and punishing people for random variation teaches nothing and the "improvement" that follows is regression to the mean |
| 📡 **Signal or Noise?** (~15 min) | SPC; problem-solving | Sixteen control charts from eight businesses. Investigate ($300) or leave alone (missing a real problem costs $2,000). Two rounds, with the Western Electric rules taught in between | Patterns, not single unusual points, separate special from common causes. Both kinds of mistake cost money. Their score (d′) shows whether they improved |
| 🎯 **The Tampering Trap** (~10 min) | Deming; SPC | Run a filling machine by hand for 15 bottles, then compare the four funnel rules | Adjusting a stable process after every measurement makes it worse (about 41 % more spread for one correction per unit) |
| 📏 **Keep the Customer** (~12 min) | SPC; capability; decision-making | Predict out-of-spec rate; sort four processes as in control or not and capable or not; find the cheapest way to Cpk ≥ 1.33 | Control limits describe the process; specification limits describe the customer. Centering is often cheaper than new equipment. Inspection sorts but doesn't improve capability |
| 💰 **Where Does the Money Go?** (~12 min) | Quality as competitive strategy; cost of quality | Classify costs as prevention, appraisal, internal or external failure; read a Pareto chart; spend a $40,000 budget across six projects | Rank problems by cost, not by count. The best portfolio is not the one a simple rule of thumb picks |
| 🧭 **Be the Quality Manager** (~10 min) | Decision-making for quality improvement | Design an inspection plan for a bottling line and see its cost over a simulated year; try again | Checking is an investment with a cost and a return. A small sample on a control chart, taken often, beats the "check and react to spec" habit |

Plus a **12-question concept check** at the start and the end (same questions, different order; answers and explanations are shown only after the final check) and a 3-minute feedback survey.

## Ways to run it

**One 75-minute class.** Warm-up check (6 min) → Red Beads and Signal or Noise (30 min) → class debrief (10 min) → Tampering Trap and Keep the Customer (22 min) → final check if time allows; the rest as homework.

**Spread over the term.** Warm-up check in week 1. Each mission on the day its topic is introduced (Red Beads with Deming, Signal or Noise with control charts, the funnel with process variation, Keep the Customer with capability, Where Does the Money Go with cost of quality, Be the Quality Manager near the end). Final check in the last week.

**Homework before a lecture.** Students do the mission before class; the lecture starts from their results (see below).

## Debrief with the class's own results

The **Instructor** page (under *For analysts & classes*) shows class-level, anonymous results for each mission, e.g. how many students warned the worker with the most red beads, how many investigated the "tempting" noise charts, how much their own adjusting widened the spread in the funnel game. Showing the class its own numbers is the most effective debrief.

The page needs research collection turned on and the instructor password (see [docs/research/SETUP.md](../docs/research/SETUP.md)). Without it, the page shows a synthetic preview so you can see what it will look like.

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

## Research use

If you want to study how much students learn, the Learning Lab can store anonymous responses from students who consent. It is **off by default**. See [docs/research/](../docs/research/) for the IRB-ready study design, consent text, setup steps and analysis script.
