# Abolish Poison + Wound Poison Stack Tracker — TBC Anniversary Resto Druid

A single Dynamic Group of icons (one per `player` / `party1..4`) that:

- Shows whether each teammate has **Abolish Poison** rolling, with a
  cooldown swipe for time remaining.
- Overlays a **red 1‑5** in the centre of the icon equal to the
  teammate's current **Wound Poison** stack count, so you can see who
  to prioritise — and stop wasting GCDs reapplying Abolish on someone
  who isn't actually being poisoned.
- No audio cue. Pure visual.

Tested against WeakAuras 2 for Burning Crusade Classic / Anniversary
(2.5.x client APIs: `UnitBuff`, `UnitDebuff` with stack count, dynamic
group children).

## Why no copy-paste wago.io string?

A wago.io export is `LibSerialize` → `LibDeflate` → base64 of the
addon's table. Producing one outside the live client is fragile (a
single field mismatch and the import silently fails). The recipe below
builds the same aura in WeakAuras' UI in ~2 minutes and is editable
forever after.

## One-time setup

1. `/wa` to open WeakAuras.
2. **New ▸ Dynamic Group** — name it `Abolish + Wound`, layout
   horizontal, sort however you like (`Hybrid` works well so missing
   buffs float to one end).
3. Inside that group: **New ▸ Icon** — name it `Unit Slot`. This single
   icon will fan out to 5 states (one per group slot) thanks to the
   Custom Status trigger.

### Trigger

- Type: **Custom**
- Event Type: **Status**
- Check On: `GROUP_ROSTER_UPDATE,UNIT_AURA,PLAYER_ENTERING_WORLD`
- Custom Trigger: paste the contents of
  [`abolish_status_trigger.lua`](./abolish_status_trigger.lua).
- Custom Untrigger: `function() return false end`
- Custom Variables (click *Add* for each):
  - `unit` — string
  - `name` — string
  - `hasAbolish` — bool
  - `stacks` — number

### Display

- Icon: leave blank — the trigger sets `state.icon` to the actual
  Abolish Poison icon when it's up, and falls back to FileID `136067`
  (`Spell_Nature_NullifyPoison`) otherwise.
- ☑ Cooldown Swipe (uses `state.duration` / `expirationTime`).
- **Custom Text** — paste [`stack_text.lua`](./stack_text.lua), set
  *Update Custom Text On* to **Every Frame**, and put `%c` somewhere
  visible. Anchor: `CENTER` of the icon, font size ~24, outline THICK,
  colour **red (1, 0, 0, 1)**.
- Add a second text region for the unit name if you want labels:
  `%name`, anchored TOP, smaller font.

### Conditions (recommended)

- If `Has Abolish` is **false** → desaturate icon, alpha 0.45. Quick
  visual for "this teammate is uncovered".
- If `Stacks` ≥ **3** → glow the icon (Pixel Glow, red). 3+ stacks is
  the priority cleanse threshold — a 5-stack Wound Poison is a 50%
  healing reduction and you usually want to top them off *before*
  cleansing or just dispel through Abolish ticks.
- If `Stacks` is **0** → the custom text already returns `""`, so no
  extra rule needed for the number.

### Load

- Player Class: **Druid**
- Talent / Spec: any (Resto in practice)
- In Group: **Yes** (optional but stops the row showing solo).

## Notes

- **Tracking by name** catches every TBC rank automatically:
  - Abolish Poison: 2893 / 8955 / 9756.
  - Wound Poison: 13218 / 13222 / 13223 / 13224 / 27189.
- **Stack semantics.** Wound Poison is a single shared debuff that
  stacks up to 5; multiple rogues do *not* multiply it past 5.
  `UnitDebuff`'s 3rd return is the live stack count, so the overlay
  matches what the rogue sees.
- **Why this beats a generic "poison applied" alert.** With this
  display you can:
  - Skip Abolish on a teammate who isn't being poisoned (saves GCDs
    and mana — Abolish is 240 mana and a 1.5s GCD).
  - Prioritise heals on whoever has the highest Wound Poison stack
    (50% healing reduction at 5 stacks is typically the kill target).
  - Notice when a teammate's Abolish actually expired vs. just got
    overwritten by a refreshing dispatch.
- **Performance.** The trigger runs on `UNIT_AURA` (only fires for
  units whose auras actually changed) plus group-roster events, so it
  won't poll every frame. The Custom Text *does* run every frame to
  keep the number in sync — that's a pure tostring on a number, so
  cost is negligible.
