# Pacelane and the recovery-first wearable bet

## A startup with one big question

Pacelane was founded in 2024 by two former cycling coaches and a sleep
researcher. The founding team had spent a decade watching elite
endurance athletes get worse on training plans that pushed them harder
on tired days. Their thesis was simple: most fitness wearables count
what athletes did; almost none measure what their bodies could safely
absorb next. The team had a hunch this gap mattered to the small
fraction of athletes who train near the edge of recovery — and that
the gap also mattered to the much larger fraction of office workers
who wanted to train hard on weekends without injuring themselves on
Monday morning runs.

The company raised a $4M seed round in early 2024 on the strength of
the founders' coaching reputations and a working prototype that
estimated recovery from overnight heart-rate-variability (HRV)
measurements. The seed pitch did not describe a strategy; it described
a problem and a piece of hardware. By month three the team had run
into the question every early-stage hardware company runs into: which
of the dozen things this device could do should we actually ship in
year one?

## Applying LVT to the recovery-first commitment

The team adopted LVT in month four after a board member who had used
it at a previous company pushed them to write down their bet
explicitly. The bet they wrote was: a recovery-focused wearable, sold
on subscription to athletes who already own a fitness tracker, will
retain at month six at a rate above 65% if the recovery score
correlates with subjective next-day readiness for at least 70% of
users. The "next-day readiness" measure came from a survey the app
prompted every morning. The 65% retention threshold was the level
above which the unit economics worked at the planned $14.99/month
subscription price.

That bet was the first time the founding team had named the test
conditions specifically enough to be falsifiable. The cycling coach
co-founder had initially wanted to bet on "Pacelane will be the most
trusted recovery tool for serious athletes," which the board member
flagged as a vision statement rather than a bet. The version that
landed traded the trust language for the retention and correlation
numbers. Several months later the team would credit that exchange
with saving them from a year of vague success criteria.

## The three initiatives that fell out of the bet

With the bet written, three initiative arcs followed. The first was
HRV measurement accuracy: the recovery score depended on a clean HRV
signal, so the hardware and firmware team owned closing the accuracy
gap against the medical-grade chest strap reference. The second was
the recovery-score model itself: the data science team owned the
correlation work between HRV-derived score and the morning-readiness
survey. The third was the athlete-facing app surface: the product
team owned a UI that would help athletes act on recovery scores
without forcing them to interpret the underlying physiology.

Each initiative had measurable outcomes named at the initiative level,
not the bet level. The accuracy initiative would ship "HRV mean
absolute error under 4 ms across the test population." The recovery
model initiative would ship "Spearman correlation 0.7 or above
against next-day-readiness on the validation panel." The app surface
initiative would ship "median time from waking to viewing recovery
score under 90 seconds." None of these were bets in their own right;
they were the concrete arcs that, together, would let the team know
whether the recovery-first bet was being tested honestly.

## Epic scope and an early pivot

Within the HRV measurement accuracy initiative, the first epic was
the seven-day HRV trend dashboard. The epic's shippable scope was a
single screen showing HRV across seven mornings with a band overlay
indicating personal baseline. The success measure was 40% adoption
of the dashboard among new subscribers within the first 90 days
post-launch. The team shipped this epic in month seven and hit 47%
adoption by day 60, surfacing that athletes were checking the trend
more than the recovery score itself in the first weeks.

The pivot moment came at month eight. The product team had drafted
an epic called "Daily Fitness Score" intended for the app surface
initiative. The score would aggregate steps, calories, sleep
duration, and recovery into one number from one to a hundred. In an
LVT review, the cycling coach co-founder asked which initiative the
epic served. The product team's answer was "all of them, kind of."
The board member ran the LVT alignment check: does this epic serve
the recovery bet? The answer was no — a daily fitness aggregate
diluted the recovery-first positioning. The epic was killed and
replaced with one called "Recovery-specific morning prompt," which
served the recovery-model initiative directly by structuring the
data the morning-readiness survey collected. The team later
described this as the moment LVT earned its keep.

## Stories, sprint discipline, and a lesson about acceptance criteria

The stories under each epic were the smallest units of weekly work.
Within the seven-day HRV trend dashboard epic, stories included
"render the seven-day chart on the home tab," "fetch HRV from the
device sync API and persist to local store," and "show personal
baseline band when fewer than 14 days of data are available."
Acceptance criteria for each story were written before sprint plan
and reviewed in code review; the data science co-founder later
estimated this single discipline cut the team's average story
re-open rate from 25% to under 8% over the next two quarters.

In month ten the team noticed a class of stories that were not
landing cleanly. These were stories that started "improve" or
"clean up" without naming what would be different when the work was
done. The fixes were small but cumulative; the LVT story-level
discipline of "what does the team do this week" surfaced that
"improve" was not an answer to that question. Stories without
acceptance criteria were reclassified as tech debt items with
explicit triggers ("revisit if average sync latency exceeds 800 ms
on the production tier") and pulled from sprint planning entirely.

## What Pacelane learned about applying LVT

Looking back from the end of year one, the team named a few things
they would do differently if they were starting again. The first was
that the bet's success criteria should have been written before the
seed raise, not four months after. The pitch deck had carried
language like "the most trusted recovery tool for serious athletes,"
which read well in investor meetings but did not commit the team to
anything they could measure against. The second was that the
correlation threshold of 0.7 had been a guess — they had no
empirical basis for picking that level versus 0.6 or 0.8 at the
time. Halfway through year one they tightened it to 0.75 after the
first internal pilot showed the device could plausibly hit the
higher bar, and the tightened threshold drove a substantive
re-architecture of the recovery model. A lower starting threshold
would have shipped a weaker model under the same LVT discipline.

Pacelane closed year one with 28,000 paying subscribers and a
month-six retention of 71% — above the 65% threshold the bet had
named. The recovery-score-to-next-day-readiness correlation landed
at 0.78. The retention number was the load-bearing evidence the
team carried into the Series A; the correlation number was what
the founders used internally to know whether to keep building. Both
numbers existed because LVT had forced them to write down what
success would look like before they started measuring it.
