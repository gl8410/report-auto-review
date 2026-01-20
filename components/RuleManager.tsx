import React, { useState, useEffect, useRef } from 'react';
import { useResizable } from '../hooks/useResizable';
import { Rule, RuleGroup } from '../types';
import { Upload, Plus, Trash2, Loader2, FolderPlus, Folder, Edit2, Download, FileUp, X, Check, ChevronRight, ChevronDown, Globe, Lock } from 'lucide-react';
import { api } from '../services/api';

// Valid options for dropdowns
const REVIEW_TYPES = ['内容完整性', '计算结果准确性', '禁止条款', '前后逻辑一致性', '措施遵从性', '计算正确性'];
const RISK_LEVELS = ['低风险', '中风险', '高风险'];

export const RuleManager: React.FC = () => {
  const [groups, setGroups] = useState<RuleGroup[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<RuleGroup | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Group creation state
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupParentId, setNewGroupParentId] = useState<string>("");
  const [newGroupType, setNewGroupType] = useState<"private" | "public">("private");
  const [isCreatingGroup, setIsCreatingGroup] = useState(false);

  // Expanded state for tree view
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Edit states
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editGroupName, setEditGroupName] = useState("");
  const [editGroupType, setEditGroupType] = useState<"private" | "public">("private");
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [editRuleData, setEditRuleData] = useState<Partial<Rule>>({});
  const [showNewRuleForm, setShowNewRuleForm] = useState(false);
  const [newRuleData, setNewRuleData] = useState<Partial<Rule>>({
    clause_number: '',
    content: '',
    review_type: '内容完整性',
    risk_level: '中风险'
  });
  const [isConfirmingDeleteGroup, setIsConfirmingDeleteGroup] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    setIsConfirmingDeleteGroup(false);
    if (selectedGroup) {
      loadRules(selectedGroup.id);
    } else {
      setRules([]);
    }
  }, [selectedGroup]);

  const loadGroups = async () => {
    try {
      const data = await api.getRuleGroups();
      setGroups(data);
    } catch (e) {
      console.error("Failed to load groups. Is backend running?", e);
    }
  };

  const loadRules = async (groupId: string) => {
    setIsLoading(true);
    try {
      const data = await api.getRules(groupId, true);
      setRules(data);
    } catch (e) {
      console.error("Failed to load rules", e);
    }
    setIsLoading(false);
  };

  const toggleExpand = (groupId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  // Helper to flatten tree for dropdown
  const flattenGroups = (groups: RuleGroup[], depth = 0): { id: string, name: string, depth: number }[] => {
    let result: { id: string, name: string, depth: number }[] = [];
    for (const group of groups) {
      result.push({ id: group.id, name: group.name, depth });
      if (group.children) {
        result = [...result, ...flattenGroups(group.children, depth + 1)];
      }
    }
    return result;
  };

  const flatGroupList = flattenGroups(groups);

  // ============== Group Operations ==============
  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      const parentId = newGroupParentId || undefined;
      await api.createRuleGroup(newGroupName, "User created group", newGroupType, parentId);
      await loadGroups(); // Reload to get updated tree
      setNewGroupName("");
      setNewGroupParentId("");
      setNewGroupType("private");
      setIsCreatingGroup(false);
    } catch (e: any) {
      alert(`Error creating group: ${e.message}`);
    }
  };

  const handleUpdateGroup = async (groupId: string) => {
    if (!editGroupName.trim()) return;
    try {
      // Pass existing parentId to avoid moving if not intended, but API handles undefined nicely?
      // Actually updateRuleGroup signature is (id, name, desc, type, parentId).
      // Here we only support renaming and changing type via inline edit for now?
      // Or just name? Use null/undefined for others if we don't want to change.
      // But we should probably keep existing values.
      const group = groups.find(g => g.id === groupId) || groups.flatMap(p => p.children || []).find(c => c.id === groupId);
      // Finding deep group is hard with flatten.
      // Let's assume we just update name and type.
      await api.updateRuleGroup(groupId, editGroupName, undefined, editGroupType);
      await loadGroups();
      setEditingGroupId(null);
      setEditGroupName("");
    } catch (e: any) {
      alert(`Update failed: ${e.message}`);
    }
  };

  const handleDeleteGroup = async (groupId: string) => {
    if (!confirm("删除规则组将同时删除其所有子组及组内规则，确定吗？")) return;
    try {
      await api.deleteRuleGroup(groupId);
      await loadGroups();
      if (selectedGroup?.id === groupId) {
        setSelectedGroup(null);
      }
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  // Recursive Tree Item Component
  const GroupTreeItem = ({ group, depth = 0 }: { group: RuleGroup, depth?: number }) => {
    const hasChildren = group.children && group.children.length > 0;
    const isExpanded = expandedGroups.has(group.id);
    const isSelected = selectedGroup?.id === group.id;
    const isEditing = editingGroupId === group.id;

    return (
      <div className="select-none">
        <div
          onClick={() => !isEditing && setSelectedGroup(group)}
          className={`flex items-center p-2 rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-50'
            }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          <div className="flex items-center gap-1 mr-1" onClick={(e) => hasChildren && toggleExpand(group.id, e)}>
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
                value={editGroupName}
                onChange={e => setEditGroupName(e.target.value)}
                onClick={e => e.stopPropagation()}
              />
               <select
                className="text-xs border rounded px-1 py-1 w-20"
                value={editGroupType}
                onChange={e => setEditGroupType(e.target.value as "private" | "public")}
                onClick={e => e.stopPropagation()}
              >
                <option value="private">私有</option>
                <option value="public">公开</option>
              </select>
              <button onClick={() => handleUpdateGroup(group.id)} className="p-1 text-green-600 hover:bg-green-50 rounded">
                <Check className="w-3 h-3" />
              </button>
              <button onClick={() => setEditingGroupId(null)} className="p-1 text-slate-400 hover:bg-slate-100 rounded">
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
                <button onClick={(e) => { e.stopPropagation(); handleDeleteGroup(group.id); }} className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded">
                  <Trash2 className="w-3 h-3" />
                </button>
                <button onClick={(e) => {
                  e.stopPropagation();
                  setEditingGroupId(group.id);
                  setEditGroupName(group.name);
                  setEditGroupType(group.type || 'private');
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
              <GroupTreeItem key={child.id} group={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  // ============== Rule Operations ==============
  const handleCreateRule = async () => {
    if (!selectedGroup || !newRuleData.clause_number?.trim() || !newRuleData.content?.trim()) {
      alert("条文号和内容不能为空");
      return;
    }
    try {
      const rule = await api.createRule(selectedGroup.id, newRuleData);
      setRules(prev => [...prev, rule]);
      setShowNewRuleForm(false);
      setNewRuleData({ clause_number: '', content: '', review_type: '内容完整性', risk_level: '中风险' });
    } catch (e: any) {
      alert(`Create rule failed: ${e.message}`);
    }
  };

  const handleUpdateRule = async (ruleId: string) => {
    try {
      const updated = await api.updateRule(ruleId, editRuleData);
      setRules(prev => prev.map(r => r.id === ruleId ? updated : r));
      setEditingRuleId(null);
      setEditRuleData({});
    } catch (e: any) {
      alert(`Update failed: ${e.message}`);
    }
  };

  const handleDeleteRule = async (id: string) => {
    if (!confirm("确定删除此规则吗？")) return;
    try {
      await api.deleteRule(id);
      setRules(prev => prev.filter(r => r.id !== id));
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  // ============== File Operations ==============
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedGroup) return;

    setIsLoading(true);
    try {
      await api.uploadRules(selectedGroup.id, file);
      setTimeout(() => loadRules(selectedGroup.id), 1500);
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCsvImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedGroup) return;
    setIsLoading(true);
    try {
      await api.importRulesCsv(selectedGroup.id, file);
      await loadRules(selectedGroup.id);
    } catch (err: any) {
      alert(`CSV import failed: ${err.message}`);
    } finally {
      setIsLoading(false);
      if (csvInputRef.current) csvInputRef.current.value = '';
    }
  };

  const handleCsvExport = async () => {
    if (!selectedGroup) return;
    try {
      await api.exportRulesCsv(selectedGroup.id, selectedGroup.name);
    } catch (err: any) {
      alert(`CSV export failed: ${err.message}`);
    }
  };

  const startEditRule = (rule: Rule) => {
    setEditingRuleId(rule.id);
    setEditRuleData({
      clause_number: rule.clause_number,
      content: rule.content,
      standard_name: rule.standard_name,
      review_type: rule.review_type,
      risk_level: rule.risk_level
    });
  };

  const { widths, handleMouseDown } = useResizable({
    clause_number: 100,
    standard_name: 160,
    content: 400,
    review_type: 120,
    risk_level: 100,
    actions: 80
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">规则管理</h2>
          <p className="text-slate-500">创建规则组，导入标准文件进行规则解析</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 h-[700px]">
        {/* Left Sidebar: Groups Tree */}
        <div className="md:col-span-3 flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-4 bg-slate-50 border-b border-slate-200">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold text-slate-700">规则组</h3>
              <button
                onClick={() => setIsCreatingGroup(!isCreatingGroup)}
                className={`p-1.5 rounded transition-colors ${isCreatingGroup ? 'bg-slate-200 text-slate-700' : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}
                title="新建规则组"
              >
                {isCreatingGroup ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
              </button>
            </div>

            {isCreatingGroup && (
              <div className="space-y-2 bg-white p-2 rounded border border-indigo-100 shadow-sm mb-2">
                <input
                  className="w-full text-sm border rounded px-2 py-1 outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="规则组名称"
                  value={newGroupName}
                  onChange={e => setNewGroupName(e.target.value)}
                  autoFocus
                />
                <div className="flex gap-2">
                  <select
                    className="flex-1 text-sm border rounded px-2 py-1 outline-none focus:ring-2 focus:ring-indigo-500"
                    value={newGroupType}
                    onChange={e => setNewGroupType(e.target.value as "private" | "public")}
                  >
                    <option value="private">私有 (Private)</option>
                    <option value="public">公开 (Public)</option>
                  </select>
                </div>
                <select
                  className="w-full text-sm border rounded px-2 py-1 outline-none focus:ring-2 focus:ring-indigo-500"
                  value={newGroupParentId}
                  onChange={e => setNewGroupParentId(e.target.value)}
                >
                  <option value="">(无父级 - 顶级组)</option>
                  {flatGroupList.map(g => (
                    <option key={g.id} value={g.id}>
                      {'\u00A0'.repeat(g.depth * 2)}{g.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleCreateGroup}
                  className="w-full py-1 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700"
                >
                  确认创建
                </button>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {groups.map(g => (
              <GroupTreeItem key={g.id} group={g} />
            ))}
            {groups.length === 0 && <div className="text-center text-xs text-slate-400 p-4">暂无规则组</div>}
          </div>
        </div>

        {/* Right Content: Rules */}
        <div className="md:col-span-9 flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          {!selectedGroup ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
              <FolderPlus className="w-16 h-16 mb-4 text-slate-200" />
              <p className="text-lg font-medium text-slate-500">选择或创建规则组</p>
              <p className="text-sm">在此管理工程标准规则</p>
            </div>
          ) : (
            <>
              <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-white sticky top-0 z-10">
                <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                  {selectedGroup.name}
                  <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-xs font-normal border border-slate-200">{rules.length} 条规则</span>
                </h3>
                <div className="flex gap-2">
                  <button onClick={() => loadRules(selectedGroup.id)} className="p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors" title="刷新">
                    <Loader2 className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  </button>
                  <button onClick={() => setShowNewRuleForm(true)} className="flex items-center px-3 py-2 bg-green-50 text-green-700 text-sm font-medium rounded-lg hover:bg-green-100 transition-colors border border-green-100" title="新建规则">
                    <Plus className="w-4 h-4 mr-1" /> 新建
                  </button>
                  <input type="file" accept=".txt,.md,.pdf,.docx" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
                  <button onClick={() => fileInputRef.current?.click()} className="flex items-center px-3 py-2 bg-indigo-50 text-indigo-700 text-sm font-medium rounded-lg hover:bg-indigo-100 transition-colors border border-indigo-100">
                    <Upload className="w-4 h-4 mr-1" /> 导入标准
                  </button>
                  <input type="file" accept=".csv" ref={csvInputRef} className="hidden" onChange={handleCsvImport} />
                  <button onClick={() => csvInputRef.current?.click()} className="flex items-center px-3 py-2 bg-amber-50 text-amber-700 text-sm font-medium rounded-lg hover:bg-amber-100 transition-colors border border-amber-100" title="导入CSV">
                    <FileUp className="w-4 h-4" />
                  </button>
                  <button onClick={handleCsvExport} className="flex items-center px-3 py-2 bg-slate-50 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-100 transition-colors border border-slate-200" title="导出CSV">
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      if (isConfirmingDeleteGroup) {
                        handleDeleteGroup(selectedGroup.id);
                        setIsConfirmingDeleteGroup(false);
                      } else {
                        setIsConfirmingDeleteGroup(true);
                      }
                    }}
                    className={`p-2 rounded-lg transition-all duration-200 ${isConfirmingDeleteGroup
                      ? 'bg-red-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-red-500 hover:bg-red-50 border border-transparent hover:border-red-100'
                      }`}
                    title={isConfirmingDeleteGroup ? "再次点击确认删除" : "删除当前规则组"}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto bg-slate-50/30">
                <table className="w-full text-left text-sm border-collapse">
                  <thead className="bg-slate-50 sticky top-0 shadow-sm text-xs uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-3 font-semibold border-b relative select-none" style={{ width: widths.clause_number }}>
                        条文号
                        <div className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-300" onMouseDown={(e) => handleMouseDown(e, 'clause_number')} />
                      </th>
                      <th className="px-4 py-3 font-semibold border-b relative select-none" style={{ width: widths.standard_name }}>
                        规范名称
                        <div className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-300" onMouseDown={(e) => handleMouseDown(e, 'standard_name')} />
                      </th>
                      <th className="px-4 py-3 font-semibold border-b relative select-none" style={{ width: widths.content }}>
                        规则内容
                        <div className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-300" onMouseDown={(e) => handleMouseDown(e, 'content')} />
                      </th>
                      <th className="px-4 py-3 font-semibold border-b relative select-none" style={{ width: widths.review_type }}>
                        审查类型
                        <div className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-300" onMouseDown={(e) => handleMouseDown(e, 'review_type')} />
                      </th>
                      <th className="px-4 py-3 font-semibold border-b relative select-none whitespace-nowrap" style={{ width: widths.risk_level }}>
                        风险等级
                        <div className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-300" onMouseDown={(e) => handleMouseDown(e, 'risk_level')} />
                      </th>
                      <th className="px-4 py-3 font-semibold border-b w-20" style={{ width: widths.actions }}>操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {/* New Rule Form Row */}
                    {showNewRuleForm && (
                      <tr className="bg-green-50/50">
                        <td className="px-4 py-2">
                          <input className="w-full text-sm border rounded px-2 py-1" placeholder="3.1.2" value={newRuleData.clause_number || ''} onChange={e => setNewRuleData({ ...newRuleData, clause_number: e.target.value })} />
                        </td>
                        <td className="px-4 py-2">
                          <input className="w-full text-sm border rounded px-2 py-1" placeholder="规范名称..." value={newRuleData.standard_name || ''} onChange={e => setNewRuleData({ ...newRuleData, standard_name: e.target.value })} />
                        </td>
                        <td className="px-4 py-2">
                          <textarea className="w-full text-sm border rounded px-2 py-1 min-h-[60px]" placeholder="规则内容..." value={newRuleData.content || ''} onChange={e => setNewRuleData({ ...newRuleData, content: e.target.value })} />
                        </td>
                        <td className="px-4 py-2">
                          <select className="w-full text-xs border rounded px-1 py-1" value={newRuleData.review_type || '内容完整性'} onChange={e => setNewRuleData({ ...newRuleData, review_type: e.target.value })}>
                            {REVIEW_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                          </select>
                        </td>
                        <td className="px-4 py-2">
                          <select className="w-full text-xs border rounded px-1 py-1" value={newRuleData.risk_level || '中风险'} onChange={e => setNewRuleData({ ...newRuleData, risk_level: e.target.value })}>
                            {RISK_LEVELS.map(i => <option key={i} value={i}>{i}</option>)}
                          </select>
                        </td>
                        <td className="px-4 py-2">
                          <div className="flex gap-1">
                            <button onClick={handleCreateRule} className="p-1 text-green-600 hover:bg-green-100 rounded"><Check className="w-4 h-4" /></button>
                            <button onClick={() => setShowNewRuleForm(false)} className="p-1 text-slate-400 hover:bg-slate-100 rounded"><X className="w-4 h-4" /></button>
                          </div>
                        </td>
                      </tr>
                    )}
                    {/* Rule Rows */}
                    {rules.map((rule) => (
                      <tr key={rule.id} className="hover:bg-slate-50 transition-colors group">
                        {editingRuleId === rule.id ? (
                          <>
                            <td className="px-4 py-2">
                              <input className="w-full text-sm border rounded px-2 py-1" value={editRuleData.clause_number || ''} onChange={e => setEditRuleData({ ...editRuleData, clause_number: e.target.value })} />
                            </td>
                            <td className="px-4 py-2">
                              <input className="w-full text-sm border rounded px-2 py-1" value={editRuleData.standard_name || ''} onChange={e => setEditRuleData({ ...editRuleData, standard_name: e.target.value })} />
                            </td>
                            <td className="px-4 py-2">
                              <textarea className="w-full text-sm border rounded px-2 py-1 min-h-[60px]" value={editRuleData.content || ''} onChange={e => setEditRuleData({ ...editRuleData, content: e.target.value })} />
                            </td>
                            <td className="px-4 py-2">
                              <select className="w-full text-xs border rounded px-1 py-1" value={editRuleData.review_type || ''} onChange={e => setEditRuleData({ ...editRuleData, review_type: e.target.value })}>
                                {REVIEW_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                              </select>
                            </td>
                            <td className="px-4 py-2">
                              <select className="w-full text-xs border rounded px-1 py-1" value={editRuleData.risk_level || ''} onChange={e => setEditRuleData({ ...editRuleData, risk_level: e.target.value })}>
                                {RISK_LEVELS.map(i => <option key={i} value={i}>{i}</option>)}
                              </select>
                            </td>
                            <td className="px-4 py-2">
                              <div className="flex gap-1">
                                <button onClick={() => handleUpdateRule(rule.id)} className="p-1 text-green-600 hover:bg-green-100 rounded"><Check className="w-4 h-4" /></button>
                                <button onClick={() => setEditingRuleId(null)} className="p-1 text-slate-400 hover:bg-slate-100 rounded"><X className="w-4 h-4" /></button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="px-4 py-3 align-top font-mono text-xs font-medium text-slate-600">{rule.clause_number}</td>
                            <td className="px-4 py-3 align-top text-xs text-slate-500">{rule.standard_name || '-'}</td>
                            <td className="px-4 py-3 align-top text-slate-700 leading-relaxed">{rule.content}</td>
                            <td className="px-4 py-3 align-top">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100">
                                {rule.review_type || '-'}
                              </span>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border
                                ${rule.risk_level === '高风险' ? 'bg-red-50 text-red-700 border-red-100' :
                                  rule.risk_level === '中风险' ? 'bg-amber-50 text-amber-700 border-amber-100' :
                                    'bg-slate-50 text-slate-600 border-slate-100'}`}>
                                {rule.risk_level}
                              </span>
                            </td>
                            <td className="px-4 py-3 align-top">
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button onClick={() => handleDeleteRule(rule.id)} className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded">
                                  <Trash2 className="w-4 h-4" />
                                </button>
                                <button onClick={() => startEditRule(rule)} className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded">
                                  <Edit2 className="w-4 h-4" />
                                </button>
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {rules.length === 0 && !isLoading && !showNewRuleForm && (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                    <p>该组暂无规则</p>
                    <p className="text-sm mt-1">上传标准文件自动提取规则，或手动新建</p>
                  </div>
                )}
                {isLoading && rules.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                    <Loader2 className="w-8 h-8 animate-spin mb-2 text-indigo-500" />
                    <p>加载中...</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};