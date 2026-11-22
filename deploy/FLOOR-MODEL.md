# THE FLOOR MODEL

As described by the owner, 2026-11-20. This is the operator workflow Myarra is
built to follow. It is written down because it has been explained verbally to
every instance and lost each time.

## The arithmetic

Scheduled hours for the shift, times sixty, is the scheduled minutes. Rate
times scheduled hours is the expected output. An operator-defined off switch
for lunch, maintenance or CIP subtracts from the scheduled time, and the
expectation falls with it.

Ten hours at 100 per hour is 1000 parts. Thirty minutes of lunch makes it 9.5
hours and 950 parts. Nothing else changes the expectation.

## Two measures, and neither of them is money

As described by the owner, 2026-11-22.

Capacity and first time quality answer different questions and must never be
netted into one number.

Run 1000 parts in an hour that owed 1000, and 25 of them are scrap. No
capacity was lost: the hour produced what it was due to produce. First time
quality suffers, 97.5 percent, and that is the other measure working as it
should.

Run 900 parts in an hour that owed 1000, none of them scrap. First time
quality is 100 percent and 100 parts of capacity are gone. Both of these are
true at once, and a single number that blends them hides whichever one the
manager needed.

So capacity compares what came off the line against what the hour was due to
produce, and scrap does not enter it. Quality compares good parts against
parts produced, and the target does not enter it. This is the same commitment
as the two measures in PHILOSOPHY, said in units rather than in OEE.

It has one consequence for the code. The capacity comparison sums
hourly_runs.units_filled, which includes scrap by the 2026-11-07 convention:
600 produced with 20 scrap is 600 total and 580 good. It does not sum
units_filled minus scrap_units. An editor who "corrects" that turns a
scrap-heavy hour at full rate into a capacity failure, and the reason demanded
of the operator would be about quality recorded as capacity.

## A shift

Monday, one shift. The line is set up. Six stations on a bottling line: glass,
which may be claret or burgundy, then rinser, filler, corker, foiler, labeler,
packer, and pallets to the warehouse.

The lead runs a line check, station by station, confirming each is set for the
job and carries no labels from the previous work order. Then a short initial
run of ten or fifteen cases goes to QA. QA passes, and production begins.

In Myarra terms: start up on the work order, sample to QA, QA approved,
production. The bot has no words for the last three yet. That is a known gap,
not a design choice.

## The hour

The line lead records hour one with a number, and the number is the count of
units produced. The system does the division, says how many minutes are
missing, and asks what happened. The operator answers in his own words,
"starting up the line, it took 15 minutes", and that sentence attaches to that
hour and appears on the hour by hour chart as the reason it was low.

No dropdown is required. The bot does the maths and calls out the gap. The
operator may answer anything. If the answer is nonsense the gap still shows on
the chart and a human sees it. That is the design, not a weakness in it.

## The switches

Lunch, maintenance and CIP are operator defined on and off switches against the
running job. They exist to subtract time from the scheduled window. They are
not a module and they are not a reason code.

Off-time duration therefore comes from the moment the switch was thrown, which
does measure duration with the clock. That is the owner's model, chosen
because a toggle pair cannot lie about when it happened. Do not "fix" it to
match the line in PHILOSOPHY about the clock ordering events, because the two
are describing different things.

## Changeover

Changeovers are where stations matter. Each station has a standard changeover
time per SKU, given to the system before production begins. Herbie asks how
long each station took and records actual against standard, per station.

Steps may run concurrently, so seven stations at thirty minutes each can
complete a changeover in thirty minutes with ten people. The aggregate standard
is therefore its own figure and never the sum of the step standards.
bot/changeover.py already carries that reasoning in a comment.

Per-station detail belongs to a PDCA question on a larger model, not to the
Herbie card, because a manager reading a list of per-station savings will add
them.

## Choosing the job

The work order carries the line it is scheduled on. If it moves, the operator
says so and says why. If the second job in the queue is not ready, running the
third is normal and needs no permission. A dropdown of that day's work orders
is acceptable.

## What this product is

A labour tracker and a continuous improvement system. Hours worked and what
came out of them. Four numbers: produced, good, reworked, scrapped, where
rework and scrap are one bucket, because both fail first time quality and
whether money is later recovered is a financial question this product does not
ask.

No material usage. No financial tracking. The plant manager is responsible for
looking at the hour by hour charts, and the onus is on him.

Constraint: three to ten million in sales, under fifty people in the whole
operation. A problem should be visible, not automated away.

## Timing

Trusting the clock at the moment a button is pressed is defensible and does not
matter much. What matters is the amount of product run during the time we said
we were running. Everything outside that window is a management issue.
