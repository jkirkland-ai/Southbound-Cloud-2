-- Custom Text function for the icon's stack overlay.
-- Paste into:  Display ▸ Custom Text  (and use `%c` as the displayed text)
--              Update Custom Text On: Every Frame   (or "On Update")
-- Color the text red (RGBA 1,0,0,1) and anchor it CENTER (or BOTTOMRIGHT)
-- of the icon. Returns "" when no Wound Poison is on the unit so the icon
-- stays clean.

function(stacks)
    if stacks and stacks > 0 then
        return tostring(stacks)
    end
    return ""
end
-- Inputs:  %stacks
