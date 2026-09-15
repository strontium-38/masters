-- scripts.lua
local M = {}

local function format_cell(v, wrap)
  if v == nil then return "" end
  v = v:gsub("^%s+", ""):gsub("%s+$", "")     -- trim
  if v == "" then return "" end

  -- numbers get \num (in an \mbox so they never break across lines)
  if v:match("^%-?%d+%.?%d*$") or v:match("^%-?%.%d+$") then
    return "\\mbox{\\num{" .. v .. "}}"
  end

  -- In a merged group cell we're inside \makecell, so allow line breaks.
  if wrap then
    return v:gsub(" ", "\\\\")   -- "Food Waste" -> "Food\\Waste"
  end
  return "\\text{" .. v .. "}"
end

-- true if a whole row is empty
local function row_is_empty(row)
  if row == nil then return true end
  for _, v in ipairs(row) do
    if v ~= nil and v:gsub("%s", "") ~= "" then
      return false
    end
  end
  return true
end

function M.emit_grouped_table(filename, ncols)
  local function split(line)
    local parts = {}
    for p in line:gmatch("([^,]*),?") do
      parts[#parts+1] = p
    end
    if parts[#parts] == "" then parts[#parts] = nil end
    return parts
  end

  local f = assert(io.open(filename, "r"))
  local rows = {}
  local first = true
  for line in f:lines() do
    if first then
      first = false
    else
      local r = split(line)
      if not row_is_empty(r) then
        rows[#rows+1] = r
      end
    end
  end
  f:close()

  local out = {}
  local i = 1
  while i <= #rows do
    -- end of group = next row with non-empty col 1
    local j = i + 1
    while j <= #rows and (rows[j][1] == nil or rows[j][1] == "") do
      j = j + 1
    end
    local n = j - i

    -- columns that should be merged (filled only on first row of group)
    local merge = {}
    if n > 1 then
      for c = 1, ncols do
        if (rows[i][c] or "") ~= "" then
          local all_blank = true
          for m = i+1, j-1 do
            if (rows[m][c] or "") ~= "" then
              all_blank = false; break
            end
          end
          if all_blank then merge[c] = true end
        end
      end
    end

    for m = i, j-1 do
      local cells = {}
      for c = 1, ncols do
        local v = rows[m][c] or ""
        if merge[c] then
          if m == i then
            cells[#cells+1] =
              "\\multirow{"..n.."}{*}{\\makecell{"..format_cell(v, true).."}}"
          else
            cells[#cells+1] = ""
          end
        else
          cells[#cells+1] = format_cell(v, false)
        end
      end
      out[#out+1] = table.concat(cells, " & ") .. " \\\\"
    end
    i = j
  end

  -- Space, not "\n" — otherwise LuaTeX tries to typeset a U+000A glyph.
  tex.sprint(table.concat(out, " "))
end

return M
