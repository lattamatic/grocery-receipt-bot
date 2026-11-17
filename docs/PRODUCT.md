# Product case study: grocery-receipt-bot

How a two-person household kept its grocery log alive after the automation tool it ran on became a paid subscription, and what I decided along the way.

## Summary

| | |
|---|---|
| **Problem** | Logging grocery spend item by item is useful and nobody wants to type it |
| **Users** | Two people in one household, sharing one spreadsheet |
| **Solution** | Send a receipt photo to a Telegram bot; every line item lands in Google Sheets |
| **My role** | Product owner and reviewer: scope, decisions, acceptance testing, PR review. The code was written with an AI coding assistant |
| **Status** | Live, replacing an earlier no-code (n8n) version |
| **Running cost** | No new subscriptions: free AI tier, free Sheets, a worker on a hosting plan I already had |

## The problem

We wanted to know what we spend on groceries at item level: not "€80 at the supermarket" but what the €80 was. Bank statements stop at the receipt total. Typing each line into a spreadsheet takes minutes per receipt, and a habit that costs minutes per shop does not survive a busy week.

I first solved this with a no-code workflow in n8n: Telegram trigger, vision model, Google Sheets. It worked, and it proved the idea. Then the 14-day trial ended. The question became whether a workflow with six nodes and two users justified a monthly subscription, or whether it could be rebuilt to run on things I already had.

## Users and the job to be done

> When I get home with a receipt, I want to capture it in one gesture, so that our spending log stays complete without either of us doing data entry.

Two constraints came from the users rather than the technology:

- **No new app.** Both of us already use Telegram. A capture flow that needs a new install or login would lose the second user.
- **One shared log.** Both people write to the same sheet, and the sheet is where analysis happens. The bot is a way in, not a destination.

## Goals and non-goals

**Goals**

1. Same user experience as the n8n version: send a photo, get a confirmation.
2. No new recurring cost.
3. Continuity of data: new rows must be indistinguishable in shape from the rows already in the sheet.
4. The user can tell when the bot may have got something wrong.

**Non-goals (for now)**

- Budgets, charts or dashboards. The spreadsheet already does this.
- Receipts other than groceries, or multi-household use.
- Perfect extraction. The aim is to be right most of the time and honest when not.

## Solution

```
Receipt photo in Telegram  →  vision model extracts JSON  →  one row per item in Google Sheets  →  summary reply
```

A message without a photo gets a short nudge to send one. Each receipt's rows share a Receipt ID, so a bad capture can be found and removed as a unit. Technical detail is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Decisions and trade-offs

| Decision | Why | What it costs |
|---|---|---|
| Keep Telegram as the only interface | Zero onboarding for either user; the habit from the n8n version carries over unchanged | No rich UI for corrections; fixes happen in the sheet |
| Keep the existing sheet schema exactly | Weeks of history stay usable with no migration | The schema inherited some choices I might not make from scratch |
| Free-tier Gemini instead of a paid vision API | Meets the "no new recurring cost" goal | Capacity is not guaranteed (see below) |
| Try the lighter model first, fall back to the larger one | In testing the larger free-tier models were frequently overloaded while the lighter one answered in seconds | Possibly lower accuracy on hard receipts; not yet measured |
| Append-only writes | The bot can never damage existing data, which made it safe to point at the real sheet from day one | Duplicates are possible and must be cleaned by hand |
| Warn when items do not add up to the receipt total | A cheap, automatic signal of a missed or misread line; it turns silent errors into visible ones | Some false alarms (rounding, deposits, vouchers) |
| Optional allowlist of chat IDs | The bot writes to a personal sheet; only known chats should be able to | A new user needs a one-time setup step |
| Long polling rather than webhooks | No public endpoint to secure; simplest thing that runs as a background worker | Only one instance can run at a time |

## What testing showed

These are observations from acceptance testing, not a benchmark.

- **Model availability mattered more than model quality.** On the day of testing, the default larger model returned "high demand" errors and timeouts; a real receipt failed after about 100 seconds. Timing six models side by side showed two lighter models answering in about 2 seconds while three larger ones failed. That one comparison changed the design from "pick the best model" to "use an ordered fallback list".
- **End to end in seconds.** Once deployed, a real receipt went from photo to saved rows in about 3 seconds.
- **The first real receipt exposed an accuracy gap.** A butcher's receipt with weighed items produced three lines summing to €26.17 against a printed total of €27.61. The same reading came back on a second attempt, which at first looked like a skipped line. This is what prompted the mismatch warning: I could not make extraction perfect in an afternoon, but I could make the failure visible to the user. The gap turned out to be tax added on top of the item prices, so the rows were right and the first version of the warning was a false alarm; the check now accepts items plus tax as a match.
- **Hidden migration work.** The old model had been retired, the bot was still registered to the old workflow's webhook, and the existing sheet had a different column layout from the first draft. None of this was visible from the workflow diagram I started from.

## How I would measure success

Nothing below is measured yet; these are the metrics I would track and the targets I would hold the product to.

| Metric | Why it matters | Target |
|---|---|---|
| Receipts captured per week, per user | The product only works if both people keep using it | No drop versus the n8n period |
| Share of receipts with a total mismatch warning | Proxy for extraction accuracy | Under 10%, trending down |
| Share of captures that fail and need a resend | Reliability of a free-tier dependency | Under 5% |
| Manual corrections in the sheet | The real cost of errors to the user | Trending down |
| Monthly running cost | The reason the rebuild exists | No new spend |

## Known limitations

- **No duplicate detection.** Sending the same receipt twice logs it twice.
- **Accuracy is unverified at scale.** One of the first real receipts had a mismatch; there is no labelled test set yet.
- **Dependence on a free tier.** Limits and model names change without notice; one model was retired between the n8n version and this one.
- **Fixed category list.** Four categories, chosen to match existing data.
- **Privacy.** Receipt images are sent to a third-party AI API for processing.

## What I would do next

1. **Duplicate detection** on store, date and total, with a "log anyway?" reply. Highest value for lowest effort, and it protects data quality.
2. **A small labelled set of real receipts** to compare models and prompts on accuracy rather than on availability alone.
3. **Corrections by reply** ("total is 27.61", "remove last receipt") so fixes do not require opening the sheet.
4. **A monthly summary message**, so the log pays the user back without them opening a spreadsheet.

## What I took from this

- A no-code prototype was the right first step: it validated the habit before any code existed. The rebuild only had to match a product that already had users.
- "Replicate the workflow" hid most of the real work. The diagram showed six boxes; the migration was in the schema, the retired model and the webhook.
- When accuracy cannot be guaranteed, designing the failure state (a clear warning, an ID to find the rows) is a product decision, not a technical afterthought.
- Reviewing through pull requests kept me in the decision seat while an AI assistant wrote the code: each change arrived with its test status and open questions, and nothing shipped unreviewed.
