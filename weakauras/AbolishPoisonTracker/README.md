# Abolish Poison Tracker — TBC Anniversary Resto Druid

A two-part WeakAura group:

1. **Poison Alert** — fires a short, recognizable sound the instant *any*
   teammate (party or raid, including you) gets a Poison-type debuff applied.
2. **Abolish Status** — five icons that show whether each party member
   currently has *Abolish Poison* up, with the buff's remaining duration.

Tested against the WeakAuras 2 build that ships for Burning Crusade
Classic / Anniversary (3.x of WeakAuras-Classic). All APIs used
(`CombatLogGetCurrentEventInfo`, `UnitDebuff` with `dispelType`/`spellId`,
`UnitBuff`, `IsInRaid`) are present in 2.5.x clients.

## Why no copy-paste wago.io string?

A wago.io / WeakAuras export string is `LibSerialize` → `LibDeflate` →
base64 of the addon's internal table. Producing one outside the live
client is brittle (a single field mismatch and the import silently
fails). The recipe below builds the same aura in under two minutes and
gives you something you can edit later.

## One-time setup

1. `/wa` to open WeakAuras.
2. **New ▸ Group** — name it `Abolish Poison Tracker`.

### Child A — "Poison Alert" (the audio cue)

1. Inside the group: **New ▸ Icon** — name it `Poison Alert`.
2. **Trigger** tab:
   - Type: **Custom**
   - Event Type: **Event**
   - Events: `COMBAT_LOG_EVENT_UNFILTERED`
   - Custom Trigger: paste the contents of
     [`poison_alert_trigger.lua`](./poison_alert_trigger.lua).
   - Duration Info (Custom): `function() return 3, 3 end` (so the icon
     auto-hides after 3s).
3. **Display** tab:
   - Icon: leave at the spell icon WA picks, or set to a poison icon
     (e.g. *Crippling Poison*, fileID `132274`).
   - Text: `%unit` (or `%c` if you bind `aura_env.lastName` via Custom Text).
4. **Actions ▸ On Show**:
   - ☑ **Play Sound**
   - **Sound by File Name (.ogg/.mp3):**
     `Sound\Interface\MapPing.wav`
     The map-ping is universally recognizable to WoW players, very short
     (≈0.3 s), and quiet enough not to drown raid callouts. Swap for any
     of these if you want a different vibe — all are short and sit well
     under voice comms:

     | Path | Feel |
     | --- | --- |
     | `Sound\Interface\MapPing.wav` *(default)* | Soft "ping" |
     | `Sound\Interface\AuctionWindowOpen.wav` | Quick chime |
     | `Sound\Interface\ReadyCheck.wav` | Sharp blip, draws eyes |
     | `Sound\Doodad\BellTollAlliance.wav` | Single bell |
     | `Sound\Spells\PVPFlagTaken.wav` | Crisp two-tone |

5. **Load** tab: Player Class **Druid**, In Group **Yes**. (Optional but
   stops it firing in solo open-world, which would be noisy.)

### Children B–F — "Abolish on <unit>" (status icons)

Five icons, one per `player`, `party1`, `party2`, `party3`, `party4`.
For each:

1. **New ▸ Icon** — name it after the unit (e.g. `Abolish - party1`).
2. **Trigger** tab:
   - Type: **Aura**
   - Buff/Debuff: **Buff**
   - Aura Name: `Abolish Poison`
   - Specific Unit: e.g. `party1`
   - Show on: **Always** (so a missing buff renders as a desaturated icon).
3. **Display** tab: enable Cooldown swipe + remaining-time text.
   *Conditions* → if "Aura Found" is false: **Desaturate** + alpha 0.4.
4. **Load** tab: Player Class **Druid**, In Group **Yes**.

If you'd rather have one dynamic icon-array that auto-resizes with the
group instead of five fixed icons, use the Custom Status trigger in
[`abolish_status_trigger.lua`](./abolish_status_trigger.lua) on a single
Dynamic Group child.

### Group layout

- Group region type: **Dynamic Group**, horizontal.
- Place the five Abolish icons in a tidy row above your party frames.
- The Poison Alert icon: drag it *out* of the dynamic group (or set its
  parent to the WA root) and anchor it to screen-center so the flash is
  unmissable but doesn't shove the row around.

## Notes & gotchas

- Detection uses the `dispelType == "Poison"` field on the actually
  applied debuff (not spell-school), so it correctly catches things like
  *Mind-Numbing Poison*, *Wyvern Sting*, *Deadly Poison*,
  *Serpent Sting*'s poison component, Naxxramas trash poisons, etc., and
  ignores unrelated Nature-school debuffs.
- The alert fires on *every* poison application — even ones Abolish
  Poison will tick off on its own. That's intentional: in TBC, Abolish
  has a 4 s tick interval and can leave a damaging poison up for that
  whole window, so you usually want to know.  If you only want to hear
  the cue when the target is *not* covered by Abolish, replace the
  `return true` line in `poison_alert_trigger.lua` with:

  ```lua
  for j = 1, 40 do
      local bn = UnitBuff(unit, j)
      if not bn then break end
      if bn == "Abolish Poison" then return false end
  end
  return true
  ```

- Abolish Poison spell IDs in TBC: 2893 / 8955 / 9756. Tracking by name
  catches all ranks automatically, so the aura works while leveling too.
- If your raid uses *Cleanse Totem* (Shaman) or other poison removal,
  the alert will still fire on the *initial* application — that's the
  point of the cue, not a bug.
