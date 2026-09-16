import csv, collections, json, io

SRC='/root/.claude/uploads/c717f55e-6a91-58d8-8717-acf476bc3193/d2a7fc52-Systems_plot_ID_mapping.csv'
rows=[r for r in csv.DictReader(open(SRC,encoding='utf-8-sig')) if r['Basic system category'].strip()]

tree=collections.defaultdict(lambda: collections.defaultdict(set))
plots=collections.Counter()
for r in rows:
    b=r['Basic system category'].strip()
    tree[b][r['Site']].add((r['System category'].strip(), r['System ID'].strip()))
    plots[(b,r['Site'])]+=1

baselines=collections.defaultdict(set)
for r in rows:
    if 'baseline' in r['System category'].lower():
        baselines[r['Site']].add(r['System category'].strip())

order=sorted(tree, key=lambda x: (-len(tree[x]), -sum(plots[(x,s)] for s in tree[x]), x))

out=io.StringIO()
W=out.write

W("""# Stage 1 — Systems mechanism narratives (working template)

**Project:** GRDC Farming Systems South (FSS) Phase 1 — Systems Hypothesis Register
**Stage 1 of 2.** You write the agronomy. Stage 2 turns it into testable statements and comes back to you for sign-off — you will not be asked to fill in a statistics grid.
**Authors:** MB, GM  **Coordination:** KS

---

## What this is, and why we are asking

The trials have been running since 2023 and the pipeline now computes yields, input
rates, costs and gross margins for all 912 plots. What it cannot do is say whether
any result *supports or contradicts what we expected*, because the project has never
written down what it expected. This document collects that.

There are two jobs on each system below.

**Job 1 — check the grouping (your call, not ours).** The 912 plots have been
collapsed into 18 "system" groups. That grouping was inferred by the data team, it is
not an agreed design, and it is very likely wrong in places. You have the final say on
it. Each system below shows you exactly which site-level treatments have been swept
into it so you can judge. Where it is wrong, split it, merge it, or re-cut it — the
pipeline will be re-keyed to whatever you decide.

**Job 2 — say what you expect, and why.** Free text. What changes under this system
relative to its comparator, through what mechanism, over what timeframe, and what
result would tell us we were wrong. Write it the way you would explain it to a grower.
Do not worry about what the pipeline can currently measure — say what you actually
think, and we will work out what is testable.

### Two things worth knowing before you start

**The grouping is demonstrably unsettled.** Two different aggregations of the same
systems already exist in the project's own files, with different labels for the same
things (`More pulses` vs `Increase pulses`, `Pulse on pulse` vs `Pulse`,
`Winter cover crop` vs `Winter cover cropping`). Nobody has ruled between them. This
is the exercise that does.

**The grouping may need a second dimension.** Several groups below are carrying a
factorial design inside a single flat label — `Intercropping (Full / Half / Nil N)`,
`Canola (High / Low / Mid N)`, `Baseline (TOS1 / TOS2)`. An earlier Hart-only file
already pulled nitrogen strategy out as its own column (High/Low/Mid/Nil), which
handles this cleanly. If a group below is really *system x N strategy* or
*system x time of sowing*, say so — that is one of the most useful things you can
tell us.

### The comparator problem — please rule on this

Almost every hypothesis is "system X versus the baseline". But **"Baseline" is 21
different treatments across the 9 sites**, and at some sites it is several at once:
Streatham has four (TOS1 High/Low/Mid N, TOS2 Mid N), Hart, Kinnabulla, Manang and
Edillilie have three each. The analysis currently pools all of them, which is almost
certainly wrong.

For each system, please nominate **which baseline it should be compared against**.
If the honest answer is "it depends on the site", say that and give the rule.

---

## How to fill this in

- Free text is fine. Bullet points are fine. Length is up to you.
- Direction matters more than magnitude. "Lower applied N, substantially" is more
  useful than a number you do not believe.
- Where you disagree with each other, both views go in. GM arbitrates at the
  reconciliation workshop; we do not need consensus in the draft.
- If you have no strong expectation for a system, write "no strong prior" — that is a
  real and useful answer, and it stops us over-reading a null result later.
- **Anything you cannot currently measure still goes in.** Fuel, labour, machinery
  passes, soil water, disease load, emissions — write the hypothesis anyway. These are
  being handled in a second pass, and this register is what will justify building them.

---
""")

W(f"\n## Coverage\n\n{len(order)} systems · {sum(plots.values())} plots · 9 sites\n\n")
W("| # | System | Sites | Plots | Site-level treatments swept in |\n|---:|---|---:|---:|---:|\n")
for i,b in enumerate(order,1):
    nv=sum(len(tree[b][s]) for s in tree[b])
    W(f"| {i} | {b} | {len(tree[b])} | {sum(plots[(b,s)] for s in tree[b])} | {nv} |\n")

W("\n### Baselines available as comparators, by site\n\n| Site | Baseline treatments |\n|---|---|\n")
for s in sorted(baselines):
    W(f"| {s} | {' · '.join(sorted(baselines[s]))} |\n")

W("\n---\n")

for i,b in enumerate(order,1):
    nsites=len(tree[b]); nplots=sum(plots[(b,s)] for s in tree[b])
    nv=sum(len(tree[b][s]) for s in tree[b])
    W(f"\n\n# {i}. {b}\n\n")
    W(f"`{nsites} site(s)` · `{nplots} plots` · `{nv} site-level treatments grouped under this name`\n\n")
    W("**What has been grouped under this system:**\n\n")
    W("| Site | Plots | System ID(s) | Treatment label(s) as recorded |\n|---|---:|---|---|\n")
    for s in sorted(tree[b]):
        labs=sorted({v[0] for v in tree[b][s]}); ids=sorted({v[1] for v in tree[b][s]})
        W(f"| {s} | {plots[(b,s)]} | {', '.join(ids)} | {'<br>'.join(labs)} |\n")

    # flag likely mis-aggregations
    allv={v[0] for s in tree[b] for v in tree[b][s]}
    flags=[]
    if len(allv)>=5:
        flags.append(f"**{len(allv)} distinct treatment labels** have been merged into this one group. Please check this is defensible.")
    if any(' N)' in v or 'N intercrop' in v for v in allv):
        flags.append("Contains **nitrogen-rate variants**. Is this one system tested at several N rates (i.e. a second dimension), or several different systems?")
    if any('TOS' in v for v in allv):
        flags.append("Contains **time-of-sowing variants (TOS)**. Same question: second dimension, or different systems?")
    if any('TOT' in v for v in allv):
        flags.append("Contains **termination-timing variants (Early/Late TOT)**. Is termination timing a treatment in its own right here?")
    if flags:
        W("\n> ⚠ **Points to check on this grouping**\n>\n")
        for f in flags: W(f"> - {f}\n")

    W(f"""
### 1.1 Grouping check — is "{b}" one system?  *(MB / GM — your call)*

| | |
|---|---|
| Coherent as a single system? | ☐ Yes  ☐ No — split  ☐ No — merge with another  ☐ Needs a second dimension |
| If split: proposed groups and the reason | |
| If merge: which group, and why | |
| If second dimension: what is it? (e.g. N strategy, TOS, termination timing) | |
| Site variants that are genuinely *different systems*, not variants | |
| Anything mislabelled or in the wrong group | |

### 1.2 Comparator — what should this be tested against?

| | |
|---|---|
| Comparator | |
| If it differs by site, state the rule | |
| Is a baseline comparison even the right test here? | |

### 1.3 Mechanism narrative  *(the main event — free text)*

**What is this system actually doing differently, and why would that change anything?**

>

**What do you expect to change, and in which direction?** Cover whatever is relevant —
crop yields, applied N and other fertiliser, herbicide/pesticide/fungicide use, number
of passes, sowing decisions, crop failures, revenue, costs, gross margin, soil water,
soil N, disease load, weed burden, fuel, labour, emissions, risk and variability.

>

**Over what timeframe?** Within season · by year 2 · over a full rotation · longer

>

**What would falsify this?** What result would tell us the expectation was wrong?

>

**How confident are you?**  ☐ High  ☐ Medium  ☐ Low  ☐ No strong prior

>

**Does this differ by site or region? Where, and why?**

>

**Anything the trial cannot show us about this system** — things you would want
measured that are not being measured, or where you expect the trial design to mislead.

>

---
""".replace("### 1.1","### %d.1"%i).replace("### 1.2","### %d.2"%i).replace("### 1.3","### %d.3"%i))

open('docs/hypothesis-register/templates/STAGE1_mechanism_narratives.md','w').write(out.getvalue())
print("wrote docs/hypothesis-register/templates/STAGE1_mechanism_narratives.md")
print("lines:", out.getvalue().count(chr(10)))
