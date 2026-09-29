-- scripts/fix-bookmarks.lua
--
-- Pandoc turns every \label{...} in a LaTeX document into a bookmark in the
-- DOCX. LaTeX labels like "ch:introduction" or "sec:general_objectives"
-- contain colons, which are illegal in XML NCName and cause LibreOffice to
-- report the whole DOCX as corrupt. This filter rewrites identifiers to use
-- only [A-Za-z0-9_.-] with a leading underscore if the first character is a
-- digit.

local function sanitize(s)
  if s == nil or s == "" then return s end
  s = s:gsub("[^%w_%-%.]", "_")
  if s:match("^%d") then s = "_" .. s end
  return s
end

function Pandoc(doc)
  return doc:walk {
    Header = function(el)
      el.identifier = sanitize(el.identifier)
      return el
    end,
    Div = function(el)
      el.identifier = sanitize(el.identifier)
      return el
    end,
    Span = function(el)
      el.identifier = sanitize(el.identifier)
      return el
    end,
  }
end
