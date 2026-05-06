-- Custom event trigger for the "Poison Alert" WeakAura.
-- Paste into:  Trigger ▸ Type: Custom ▸ Event Type: Event
--              Event(s):  COMBAT_LOG_EVENT_UNFILTERED
--              Custom Trigger:  (this whole function)
--
-- Fires once whenever a Poison-type debuff is applied or refreshed on a
-- player in your party/raid (including yourself). The aura's "On Show"
-- action plays the sound cue.

function(event)
    if event ~= "COMBAT_LOG_EVENT_UNFILTERED" then return false end

    local _, subevent, _, _, _, _, _, destGUID, _, destFlags, _,
          spellID, _, _, auraType = CombatLogGetCurrentEventInfo()

    if subevent ~= "SPELL_AURA_APPLIED" and subevent ~= "SPELL_AURA_REFRESH" then
        return false
    end
    if auraType ~= "DEBUFF" then return false end

    -- Friendly target only.
    if bit.band(destFlags or 0, COMBATLOG_OBJECT_REACTION_FRIENDLY) == 0 then
        return false
    end

    -- Resolve destGUID to a unit token in our group.
    local unit
    if UnitGUID("player") == destGUID then
        unit = "player"
    else
        local prefix, count
        if IsInRaid() then
            prefix, count = "raid", 40
        else
            prefix, count = "party", 4
        end
        for i = 1, count do
            local u = prefix .. i
            if UnitGUID(u) == destGUID then unit = u; break end
        end
    end
    if not unit then return false end

    -- Confirm the just-applied aura is actually a Poison (dispelType == "Poison").
    for i = 1, 40 do
        local name, _, _, dispelType, _, _, _, _, _, dSpellID = UnitDebuff(unit, i)
        if not name then break end
        if dSpellID == spellID and dispelType == "Poison" then
            -- Stash the unit for the untrigger / display, if you want to use %unit.
            aura_env.lastUnit  = unit
            aura_env.lastName  = UnitName(unit)
            aura_env.lastSpell = name
            return true
        end
    end

    return false
end

-- Optional Untrigger (Custom): hide after ~3s so the icon flash auto-dismisses.
-- Use a separate "Duration Info" function instead if you want a timed bar:
--
-- function() return 3, 3 end
