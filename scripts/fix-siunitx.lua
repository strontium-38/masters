-- scripts/fix-siunitx.lua
-- Rewrite \unit{...} blocks in math so Pandoc's texmath can convert them
-- to OMML. Handles siunitx prefixes + base units and the custom units
-- declared with \DeclareSIUnit in preamble.sty.

local prefixes = {
  ["\\mega"]  = "M",
  ["\\kilo"]  = "k",
  ["\\milli"] = "m",
  ["\\micro"] = "\\mu ",
}

local units = {
  ["\\gram"]    = "g",
  ["\\litre"]   = "L",
  ["\\liter"]   = "L",
  ["\\meter"]   = "m",
  ["\\metre"]   = "m",
  ["\\second"]  = "s",
  ["\\minute"]  = "min",
  ["\\hour"]    = "h",
  ["\\day"]     = "d",
  ["\\year"]    = "yr",
  ["\\yr"]      = "yr",
  ["\\celsius"] = "{}^{\\circ}C",
  ["\\mol"]    = "mol",
  ["\\mole"]    = "mol",
  ["\\newton"]  = "N",
  ["\\joule"]   = "J",
  ["\\watt"]    = "W",
  ["\\volt"]    = "V",
  ["\\ampere"]  = "A",
  ["\\kelvin"]  = "K",
  ["\\percent"] = "\\%",
  -- custom from preamble.sty
  ["\\nml"]          = "NmL",
  ["\\normality"]    = "N",
  ["\\dil"]          = "X",
  ["\\molar"]        = "M",
  ["\\gforce"]       = "G",
  ["\\tonne"]        = "t",
  ["\\VSfed"]        = "VS_{fed}",
  ["\\VS"]           = "VS",
  ["\\reactorlitre"] = "L_{r}",
  ["\\CHCOOH"]       = "CH_{3}COOH",
  ["\\CaCO"]         = "CaCO_{3}",
  ["\\NaOH"]         = "NaOH",
  ["\\CO"]           = "CO_{2}",
  ["\\CH"]           = "CH_{4}",
  ["\\COD"]          = "COD",
  ["\\NL"]           = "NL",
}

local function read_macro(s, i)
  local j = i + 1
  while j <= #s and s:sub(j, j):match("%a") do j = j + 1 end
  return s:sub(i, j - 1), j
end

local function read_group(s, i)
  -- s:sub(i,i) must be "{"
  local depth, j = 1, i + 1
  while j <= #s and depth > 0 do
    local c = s:sub(j, j)
    if c == "{" then depth = depth + 1
    elseif c == "}" then depth = depth - 1 end
    j = j + 1
  end
  return s:sub(i + 1, j - 2), j
end

local function skip_ws(s, i)
  while i <= #s and s:sub(i, i):match("%s") do i = i + 1 end
  return i
end

local function expand_unit(content)
  local atoms, pending = {}, ""
  local i, n = 1, #content

  while i <= n do
    local c = content:sub(i, i)
    if c == "\\" then
      local m, j = read_macro(content, i)
      if m == "\\per" then
        atoms[#atoms+1] = "/"
        i = j
      elseif m == "\\cubic" or m == "\\squared" then
        local k = skip_ws(content, j)
        if content:sub(k, k) == "\\" then
          local base, l = read_macro(content, k)
          local base_txt = units[base] or base
          local exp = (m == "\\cubic") and "^{3}" or "^{2}"
          atoms[#atoms+1] = pending .. base_txt .. exp
          pending = ""
          i = l
        else
          atoms[#atoms+1] = pending .. m
          pending = ""
          i = j
        end
      elseif m == "\\raiseto" or m == "\\tothe" then
        local k = skip_ws(content, j)
        if content:sub(k, k) == "{" then
          local arg, l = read_group(content, k)
          if #atoms > 0 then
            atoms[#atoms] = atoms[#atoms] .. "^{" .. arg .. "}"
          else
            atoms[#atoms+1] = pending .. "^{" .. arg .. "}"
            pending = ""
          end
          i = l
          local p = skip_ws(content, i)
          if content:sub(p, p+2) == "\\of" then i = p + 3 end
        else
          i = j
        end
      elseif m == "\\of" then
        local k = skip_ws(content, j)
        if content:sub(k, k) == "{" then
          local _, l = read_group(content, k)
          i = l
        else
          i = j
        end
      elseif prefixes[m] then
        pending = pending .. prefixes[m]
        i = j
      else
        local txt = units[m] or m
        atoms[#atoms+1] = pending .. txt
        pending = ""
        i = j
      end
    else
      if not c:match("%s") then
        atoms[#atoms+1] = c
      end
      i = i + 1
    end
  end
  if pending ~= "" then atoms[#atoms+1] = pending end

  -- Join atoms with explicit `\ ` between consecutive non-slash atoms.
  local out = {}
  for idx, a in ipairs(atoms) do
    out[#out+1] = a
    local nxt = atoms[idx + 1]
    if nxt and a ~= "/" and nxt ~= "/" then
      out[#out+1] = "\\ "
    end
  end
  return table.concat(out)
end

local function rewrite_unit_blocks(t)
  local out, i = {}, 1
  while true do
    local s, e = t:find("\\unit%s*{", i)
    if not s then
      out[#out+1] = t:sub(i)
      break
    end
    out[#out+1] = t:sub(i, s - 1)
    local content, j = read_group(t, e)   -- content of { ... }, j = after }
    out[#out+1] = "\\mathrm{" .. expand_unit(content) .. "}"
    i = j
  end
  return table.concat(out)
end

function Math(el)
  if el.mathtype == "DisplayMath" or el.mathtype == "InlineMath" then
    el.text = rewrite_unit_blocks(el.text)
    return el
  end
  return nil
end
