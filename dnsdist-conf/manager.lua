-- ver 0.0.4
webconsole_lists = {}

ListManager = {
  lists = webconsole_lists or {}
}

function ListManager:new(lists)
  local obj = { lists = lists or {} }
  setmetatable(obj, self)
  self.__index = self
  return obj
end

function ListManager:remove_list(list_name)
  if self.lists[list_name] then
    self.lists[list_name] = nil 
    out = list_name .. "Deleted\n"
    return out
  else
    out = "not list"
    return out
  end
end

function ListManager:add(list_name, value)
  if not self.lists[list_name] then
    self.lists[list_name] = {}
  end
  
  for _, v in ipairs(self.lists[list_name]) do
    if v == value then
      return "Value already exists in " .. list_name .. ": " .. value
    end
  end
  
  table.insert(self.lists[list_name], value)
  return "Add Done: " .. list_name .. " " .. value
end

function ListManager:remove(list_name, value)
  if not self.lists[list_name] then return false end
  
  for i, v in ipairs(self.lists[list_name]) do
    if v == value then
      table.remove(self.lists[list_name], i)
      out = "Delete Done:" .. list_name .. " " .. value
      return out
    end
  end

  return out
end

function ListManager:show_all()
  local out = ""
  
  for name, data in pairs(self.lists) do
    out = out .. "[" .. name .. "]\n"
    for i, value in ipairs(data) do
      out = out .. value .. "\n"

    end
      out = out .. "\n"
  end
  
  if out == "" then
    out = "Empty lists"
  end
  
  return out
end

function ListManager:show_list(list_name)
  if not self.lists[list_name] then
    return "List '" .. list_name .. "' not found\n"
  end
  
  local out = "[" .. list_name .. "]\n"
  for i, value in ipairs(self.lists[list_name]) do
    out = out .. "  " .. i .. ". " .. value .. "\n"
  end
  
  return out
end


manager = ListManager:new(webconsole_lists)
