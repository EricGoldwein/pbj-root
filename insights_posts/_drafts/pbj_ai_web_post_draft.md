# How to Use PBJ Data with Claude, ChatGPT, or Whatever Robot You Currently Trust

If you are one of the lucky dozen or so people who made it to this page, you probably already know how to use AI.

You might have already uploaded this article to ChatGPT for a summary. You might have asked Claude whether PBJ320 is a legitimate site. It is. You might have asked Gemini what PBJ stands for and pretended you knew already.

That is fine. You are busy. You would probably rather watch a Yankees game, drink a beer, scroll TikTok, answer one more email, or do basically anything else besides read another “how to use AI” guide from a Brooklyn millennial with a public-data problem.

So I’ll keep this useful.

**Fast version:** use real data, ask specific questions, make the AI cite numbers, and do not let a clean paragraph substitute for judgment.

[Button: Open CMS Care Compare]  
[Button: Open ProPublica Nursing Home Inspect]  
[Button: Try a PBJ320 Prompt]

---

## The Data Is Public. Check Me.

PBJ stands for **Payroll-Based Journal**. It is staffing data that nursing homes submit to CMS.

You do not need PBJ320 to access PBJ data. CMS publishes it. You can pull it yourself. You should, if you want to.

Useful places to start:

- **CMS Care Compare** — the consumer-facing federal nursing home lookup tool.
- **CMS public datasets** — the rawer stuff, including PBJ staffing files.
- **ProPublica Nursing Home Inspect** — a strong independent lookup tool built from public inspection data.
- **State inspection and enforcement sites** — often clunky, sometimes essential.
- **Cost reports, ownership data, and other public records** — not always fun, often useful.

PBJ320 is my attempt to make some of this easier to use, especially for people who are not excited to spend their afternoon fighting with federal CSVs.

But the source matters more than the wrapper.

Do not trust a dashboard because it looks clean.  
Do not trust an AI summary because it sounds confident.  
Do not trust me because I have a logo.

Check the source.

> **Modal / footnote: Where PBJ data comes from**  
> PBJ staffing data is submitted by nursing homes to CMS. It is public federal data. PBJ320 organizes and interprets pieces of that data, but it is not the original source. Users should verify important findings against CMS data, Care Compare, facility records, state sources, and other primary documents.

---

## What PBJ Can Tell You

The main PBJ number people talk about is **HPRD** — hours per resident day.

At the simplest level, PBJ helps answer:

> How much reported staff time did this nursing home have, by role, compared with its resident census?

That is useful.

PBJ can help show:

- low RN staffing;
- heavy reliance on aides;
- changes over time;
- weekend patterns;
- ownership/operator shifts;
- odd quarters;
- facilities that look unusual compared with peers.

But PBJ does **not** automatically tell you:

- whether neglect occurred;
- whether a specific resident was harmed;
- whether a facility violated the law;
- what happened on one shift;
- whether staffing was enough for the residents actually living there.

PBJ is evidence. It is not the whole case.

> **Suggested image slot:** screenshot of a PBJ320 facility page showing RN / aide / total nurse staffing trends.  
> **Caption:** PBJ can help surface patterns. It cannot, by itself, explain everything happening inside a facility.

---

## How AI Helps — and How It Goes Wrong

AI is pretty good at turning ugly data into readable language.

That is useful.

It is also pretty good at turning limited evidence into overconfident conclusions.

Bad prompt:

> Is this nursing home understaffed?

Better prompt:

> Use the attached PBJ data. Explain what the data shows, what it may suggest, what it cannot prove, and what questions a family member, advocate, journalist, attorney, or ombudsman should ask next.

That is the difference between using AI as an analyst and using it as a drunk intern with excellent grammar.

---

## Seven Rules

### 1. Give it real data

Use CMS data. Use Care Compare. Use ProPublica. Use PBJ320. Use a CSV. Use a facility page. Use a downloaded packet if there is one.

But give it something concrete.

Do not ask AI to guess.

### 2. Make it cite numbers

Ask:

> What exact data points support this conclusion?

If it says staffing is “concerning,” make it show why.

Was RN HPRD low? Compared with what? State median? National median? The facility’s own history? CMS case-mix reference? A state minimum? A made-up vibe?

AI loves adjectives. Make it earn them.

### 3. Watch census

HPRD depends on resident census.

A facility can look better because it added staff.

It can also look better because it had fewer residents.

This matters a lot around COVID, when census dropped and HPRD often rose. It also matters when comparing facilities, quarters, and ownership changes.

Do not just ask whether HPRD changed.

Ask why.

### 4. One quarter is not a personality

One bad quarter can matter.

But one quarter is not the whole facility.

Ask whether the pattern persists. Ask whether it is unusual for that facility. Ask whether RN staffing moved differently than aide staffing. Ask whether census changed. Ask whether there are missing quarters.

The trend is usually more interesting than the snapshot.

### 5. PBJ is not proof of causation

PBJ can raise questions. It can support a theory. It can identify staffing context. It can help shape reporting, advocacy, oversight, or discovery.

But it does not prove that a resident was harmed because of staffing.

Better:

> The PBJ data raises questions about staffing during this period.

Worse:

> The PBJ data proves the facility caused harm.

The first may be useful.

The second may be bullshit.

### 6. Match the output to the person using it

A family member does not need the same memo as an attorney.

A journalist does not need the same memo as an ombudsman.

A policymaker does not need the same memo as a daughter trying to understand why her mother’s call bell keeps going unanswered.

Same data. Different job.

This is where good prompting matters. Tell the AI who the output is for.

> **Modal / accordion: Prompt examples by audience**
>
> **Family member:** “Explain this facility’s staffing in plain English. What stands out? What should I ask the administrator?”
>
> **Advocate:** “Summarize staffing patterns, possible red flags, limits of the data, and follow-up questions for resident advocacy.”
>
> **Journalist:** “Identify the strongest data-supported angle, comparison points, caveats, and records needed before publication.”
>
> **Attorney:** “Use PBJ as staffing context only. Identify relevant patterns and discovery questions. Do not imply causation without additional evidence.”
>
> **Ombudsman:** “Focus on oversight questions, resident impact, and what should be verified through interviews, care records, staffing schedules, and facility response.”

### 7. Read the output like a skeptical person

People can tell when something is lazily AI-written.

Maybe they cannot explain why. But they can feel it. The fake balance. The smooth paragraphs. The dead phrases. “Robust.” “Crucial.” “It is important to note.” “This underscores.”

Use AI to organize. Use it to summarize. Use it to draft. Use it to find questions.

Then edit it like someone who knows what they are talking about.

---

## Which AI Tool Should You Use?

Probably the one you already use.

Claude is good with long documents. ChatGPT is good for back-and-forth analysis and structured workflows. Gemini is there if you live in Google.

Do not turn model choice into theology.

Clean data and a decent prompt matter more than picking the fanciest robot.

> **Modal / footnote: What about Claude Skills, GPTs, and plugins?**  
> PBJ320 is experimenting with AI-friendly prompts, downloadable data packets, and eventually more structured ways for AI tools to work with public nursing home data. The boring version: better inputs, better instructions, fewer hallucinations. The nerdier version: public staffing data should become easier for AI tools to query without guessing.

---

## Where PBJ320 Fits

PBJ320 is not the source of truth.

The public data is the source of truth.

PBJ320 is a tool for making that data easier to read, question, and use.

Some of this is basic: facility pages, prompts, CSVs, summaries.

Some of it may get more advanced: AI-friendly packets, Claude Skills, GPT workflows, and maybe more direct integrations later.

But the goal is not to make people dependent on PBJ320.

The goal is to make the public data harder to ignore and harder to misuse.

> **Suggested image slot:** screenshot of CMS Care Compare next to PBJ320 / ProPublica source links.  
> **Caption:** Start with public sources. Use tools to organize the evidence, not replace it.

---

## How This Article Happened

This article came from reading about CourtListener becoming available inside Claude.

I asked ChatGPT what I could learn from it.

The useful point was not “AI is the future.” Spare me.

The useful point was that CourtListener is trying to make legal data easier for AI tools to use without forcing the AI to make things up.

That seemed relevant.

PBJ data has a similar problem in miniature. The data exists. It is public. It is technically accessible. But “technically accessible” is not the same thing as usable.

So I used AI to think through the idea, drafted something, realized it sounded too much like AI, complained about that, revised it, and will probably revise it again once it is on the page.

That is probably the honest version of how a lot of writing works now.

The trick is not pretending AI was not involved.

The trick is not letting it turn everything into beige paste.

> **Modal / accordion placement:** Hide this full “How this article happened” section behind a link: “How I used AI to write this.” It is useful and honest, but it should not interrupt the main post.

---

## The Point

Use AI.

Use CMS.

Use Care Compare.

Use ProPublica.

Use PBJ320 if it helps.

Just do not confuse a clean summary with the truth.

The truth is still in the source data, the records, the building, and the people living there.

AI can help you get to better questions faster.

That is enough.

---

# Implementation Notes for Cursor

## Page structure

Use this as a web post, not a long static essay. Keep the main visible page short and readable.

Recommended visible sections:

1. Hero / intro
2. The Data Is Public. Check Me.
3. What PBJ Can Tell You
4. How AI Helps — and How It Goes Wrong
5. Seven Rules
6. Which AI Tool Should You Use?
7. Where PBJ320 Fits
8. The Point

## Modal / accordion candidates

Hide these behind expandable UI:

- Where PBJ data comes from
- Prompt examples by audience
- What about Claude Skills, GPTs, and plugins?
- How this article happened

## Links to include

Add real hyperlinks for:

- CMS Care Compare
- CMS public PBJ datasets
- ProPublica Nursing Home Inspect
- PBJ320 facility lookup
- PBJ320 prompt page or prompt modal, when available
- Claude Skill / GPT prompt links, when available

## Images to incorporate

Use images/screenshots from the site if available:

- PBJ320 facility trend screenshot
- PBJ320 state/facility lookup screenshot
- Example prompt card or copy-prompt UI
- Source comparison image: CMS / ProPublica / PBJ320

Keep screenshots functional, not decorative.

## Tone guardrails

Avoid:

- “unlock insights”
- “leverage AI”
- “robust”
- “transformative”
- “empower stakeholders”
- “it is important to note”
- generic responsible-AI language

Prefer:

- direct claims
- concrete caveats
- public-data humility
- skepticism toward both dashboards and AI
- PBJ320 as useful tool, not sacred object

