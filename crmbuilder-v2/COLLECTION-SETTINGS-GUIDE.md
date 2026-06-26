# Setting How a Record List Sorts and Searches

*A plain-language guide for setting an entity's list and search behaviour in the
CRM Builder app. No technical steps required.*

## What these settings do

Every type of record — Mentor Profile, Account, Engagement, and so on — has a few
settings that control how its **list** behaves and how its **search box** works.
There are five of them:

| Setting | What it controls |
|---|---|
| **Default sort field** | Which field the list is ordered by when you open it. |
| **Default sort direction** | Whether that order runs A→Z / oldest-first (**asc**) or Z→A / newest-first (**desc**). |
| **Quick-search fields** | Which fields the search box looks inside when someone types in it. |
| **Full-text search** | Turns the deeper "search everything" mode on or off. |
| **Full-text search min length** | (Optional) How many letters someone must type before full-text search starts. |

These settings only change how lists are **ordered and searched** — they never
change any of your data.

## How to change them

1. Open the **CRM Builder** app.
2. In the left-hand sidebar, click **Entities**.
3. Click the record type you want to change (for example, *Mentor Profile*).
4. Click **Edit**.
5. Scroll down to these boxes and fill in the ones you want:

   - **Default sort field** — type the field to sort by, using its short internal
     name (for example, `lastName`).
   - **Default sort direction** — choose **asc** or **desc**.
   - **Quick-search fields** — type the fields the search box should search,
     separated by commas (for example, `name, emailAddress`).
   - **Full-text search** — choose **true** to turn it on, or **false** to leave it off.
   - **Full-text search min length** — leave blank, or type a number.

6. Click **Save**.

## How to check it worked

- **Quick check:** reopen the same record type and click **Edit** again — your
  settings should still be filled in exactly as you left them.
- **In the live CRM:** once the settings have been published to the live system,
  open that record type's list — it should now sort and search the way you set it.

## Good to know

- The **field name** is the short internal name (like `lastName` or `emailAddress`),
  **not** the friendly label you see on the screen. If you're not sure of a field's
  internal name, ask whoever set up the CRM.
- Leave any box **blank** to keep the standard default.
- The very same five settings also live in EspoCRM itself, under
  **Administration → Entity Manager** (as *Order By*, *Sort Direction*,
  *Text Filter Fields*, *Full-Text Search*). Setting them in CRM Builder keeps them
  recorded in one place and lets them be re-applied to the CRM automatically.
