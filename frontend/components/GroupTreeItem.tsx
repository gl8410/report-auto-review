import React, { useState, useEffect } from 'react';
import { RuleGroup } from '../types';
import { ChevronDown, ChevronRight, Folder, Globe, Lock, Check, X, Trash2, Edit2 } from 'lucide-react';

interface GroupTreeItemProps {
  group: RuleGroup;
  depth?: number;
  expandedGroups: Set<string>;
  selectedGroup: RuleGroup | null;
  editingGroupId: string | null;
  
  onToggleExpand: (groupId: string, e: React.MouseEvent) => void;
  onSelectGroup: (group: RuleGroup) => void;
  onStartEdit: (group: RuleGroup) => void;
  onSaveEdit: (groupId: string, name: string, type: "private" | "public") => void;
  onCancelEdit: () => void;
  onDeleteGroup: (groupId: string) => void;
}

const GroupTreeItem: React.FC<GroupTreeItemProps> = React.memo(({
  group,
  depth = 0,
  expandedGroups,
  selectedGroup,
  editingGroupId,
  onToggleExpand,
  onSelectGroup,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onDeleteGroup
}) => {
  const hasChildren = group.children && group.children.length > 0;
  const isExpanded = expandedGroups.has(group.id);
  const isSelected = selectedGroup?.id === group.id;
  const isEditing = editingGroupId === group.id;

  // Local state for editing ensures typing is performant and isolation matches
  const [localName, setLocalName] = useState(group.name);
  const [localType, setLocalType] = useState<"private" | "public">(group.type || "private");

  // Sync state when entering edit mode
  useEffect(() => {
    if (isEditing) {
      setLocalName(group.name);
      setLocalType(group.type || "private");
    }
  }, [isEditing, group.name, group.type]);

  return (
    <div className="select-none">
      <div
        onClick={() => !isEditing && onSelectGroup(group)}
        className={`flex items-center p-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-50'
          }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <div className="flex items-center gap-1 mr-1" onClick={(e) => hasChildren && onToggleExpand(group.id, e)}>
          {hasChildren ? (
            isExpanded ? <ChevronDown className="w-3 h-3 text-slate-400" /> : <ChevronRight className="w-3 h-3 text-slate-400" />
          ) : (
            <div className="w-3" />
          )}
        </div>

        {isEditing ? (
          <div className="flex items-center gap-1 flex-1" onClick={e => e.stopPropagation()}>
            <input
              className="flex-1 text-sm border rounded px-2 py-1 min-w-0"
              value={localName}
              onChange={e => setLocalName(e.target.value)}
              onClick={e => e.stopPropagation()}
              autoFocus
            />
             <select
              className="text-xs border rounded px-1 py-1 w-20"
              value={localType}
              onChange={e => setLocalType(e.target.value as "private" | "public")}
              onClick={e => e.stopPropagation()}
            >
              <option value="private">私有</option>
              <option value="public">公开</option>
            </select>
            <button onClick={() => onSaveEdit(group.id, localName, localType)} className="p-1 text-green-600 hover:bg-green-50 rounded">
              <Check className="w-3 h-3" />
            </button>
            <button onClick={onCancelEdit} className="p-1 text-slate-400 hover:bg-slate-100 rounded">
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <Folder className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'fill-indigo-200' : ''}`} />
              <span className="truncate text-sm font-medium">{group.name}</span>
              {group.type === 'public' ? (
                <Globe className="w-3 h-3 text-slate-400" title="Public" />
              ) : (
                <Lock className="w-3 h-3 text-slate-300" title="Private" />
              )}
            </div>
            <div className="hidden group-hover:flex items-center gap-1 opacity-0 hover:opacity-100">
              <button onClick={(e) => { e.stopPropagation(); onDeleteGroup(group.id); }} className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded">
                <Trash2 className="w-3 h-3" />
              </button>
              <button onClick={(e) => {
                e.stopPropagation();
                onStartEdit(group);
              }} className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded">
                <Edit2 className="w-3 h-3" />
              </button>
            </div>
          </>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div>
          {group.children!.map(child => (
            <GroupTreeItem
              key={child.id}
              group={child}
              depth={depth + 1}
              expandedGroups={expandedGroups}
              selectedGroup={selectedGroup}
              editingGroupId={editingGroupId}
              onToggleExpand={onToggleExpand}
              onSelectGroup={onSelectGroup}
              onStartEdit={onStartEdit}
              onSaveEdit={onSaveEdit}
              onCancelEdit={onCancelEdit}
              onDeleteGroup={onDeleteGroup}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export default GroupTreeItem;