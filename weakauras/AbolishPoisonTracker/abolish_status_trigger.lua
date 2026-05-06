-- Custom Status trigger for the "Abolish Poison + Wound Poison stacks" group.
-- Emits one state per group slot (player + party1..4) so a Dynamic Group of
-- icons auto-arranges itself.
--
-- Wire-up in WeakAuras:
--   Trigger ▸ Type: Custom ▸ Event Type: Status
--   Check On:  GROUP_ROSTER_UPDATE, UNIT_AURA, PLAYER_ENTERING_WORLD
--   Custom Trigger:  this function
--   Custom Untrigger: function() return false end
--
--   Custom Variables (so WA exposes them in Display/Conditions):
--     unit       = "string"
--     name       = "string"
--     hasAbolish = "bool"
--     stacks     = "number"
--
-- The state also fills `icon`, `duration`, `expirationTime`, `progressType`,
-- and `value/total` so a Cooldown swipe and a "%stacks" text just work.

function(allstates)
    local units   = { "player", "party1", "party2", "party3", "party4" }
    local ABOLISH = "Abolish Poison"
    local WOUND   = "Wound Poison"
    local FALLBACK_ICON = 136067 -- Spell_Nature_NullifyPoison (Abolish Poison)

    for _, unit in ipairs(units) do
        local state = allstates[unit] or { unit = unit }

        if UnitExists(unit) then
            local aIcon, aDur, aExp
            for i = 1, 40 do
                local n, ic, _, _, dur, exp = UnitBuff(unit, i)
                if not n then break end
                if n == ABOLISH then
                    aIcon, aDur, aExp = ic, dur or 0, exp or 0
                    break
                end
            end

            local wStacks = 0
            for i = 1, 40 do
                local n, _, count = UnitDebuff(unit, i)
                if not n then break end
                if n == WOUND then
                    wStacks = (count and count > 0) and count or 1
                    break
                end
            end

            state.show           = true
            state.changed        = true
            state.unit           = unit
            state.name           = UnitName(unit) or unit
            state.icon           = aIcon or FALLBACK_ICON
            state.hasAbolish     = aIcon ~= nil
            state.stacks         = wStacks
            state.progressType   = aIcon and "timed" or "static"
            state.duration       = aDur or 0
            state.expirationTime = aExp or 0
            state.value          = wStacks
            state.total          = 5
            state.autoHide       = false
        else
            state.show    = false
            state.changed = true
        end

        allstates[unit] = state
    end

    return true
end
