-- Optional secondary trigger used by each per-unit Abolish Poison icon.
-- The simplest way is to use the built-in Aura trigger:
--
--   Trigger ▸ Type: Aura
--   Buff/Debuff: Buff
--   Aura Name: Abolish Poison
--   Specific Unit: party1   (one icon per unit: party1..party4 + player)
--   Show on: Always (so you see "missing" state too)
--
-- If you prefer a single dynamic-group trigger, use this Custom Aura
-- function instead, which returns one entry per group member.
--
-- Trigger ▸ Type: Custom ▸ Event Type: Status
--   Check On:  Every Frame  (or  GROUP_ROSTER_UPDATE,UNIT_AURA)
--   Custom Trigger:  the function below
--   Custom Untrigger: function() return false end
--   Custom Variables: { unit = "string", remaining = "number", hasBuff = "bool" }
--   In "Display ▸ Dynamic Info" return: { name, icon, duration, expiration, ... }

function(allstates)
    local units = { "player", "party1", "party2", "party3", "party4" }
    local SPELL = "Abolish Poison"
    local now = GetTime()

    for _, unit in ipairs(units) do
        if UnitExists(unit) then
            local name, icon, _, _, duration, expiration = nil, nil, nil, nil, 0, 0
            for i = 1, 40 do
                local n, ic, _, _, dur, exp, _, _, _, sId = UnitBuff(unit, i)
                if not n then break end
                if n == SPELL then
                    name, icon, duration, expiration = n, ic, dur or 0, exp or 0
                    break
                end
            end

            local guid = UnitGUID(unit) or unit
            local state = allstates[guid] or {}
            state.show       = true
            state.changed    = true
            state.unit       = unit
            state.name       = UnitName(unit) or unit
            state.icon       = icon or 136075   -- abolish poison icon fallback
            state.hasBuff    = name ~= nil
            state.progressType = "timed"
            state.duration   = duration
            state.expirationTime = expiration
            state.autoHide   = false
            allstates[guid]  = state
        else
            local guid = UnitGUID(unit) or unit
            if allstates[guid] then
                allstates[guid].show = false
                allstates[guid].changed = true
            end
        end
    end
    return true
end
