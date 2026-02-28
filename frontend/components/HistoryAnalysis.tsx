import React, { useState, useEffect, useRef } from 'react';
import { HistoryAnalysisTask, InferredOpinion, RuleGroup } from '../types';
import { api } from '../services/api';
import { FileUp, Loader2, AlertCircle, CheckCircle2, XCircle, ArrowRight, Save, Trash2, Edit2, FileText, RefreshCw, ChevronRight, ChevronDown, Folder } from 'lucide-react';
import { DocumentViewer } from './DocumentViewer';

interface GroupTreeCheckboxProps {
    group: RuleGroup;
    depth?: number;
    expandedGroups: Set<string>;
    selectedGroupIds: string[];
    onToggleExpand: (id: string) => void;
    onCheck: (id: string, checked: boolean) => void;
}

const GroupTreeCheckbox: React.FC<GroupTreeCheckboxProps> = ({ 
    group, 
    depth = 0, 
    expandedGroups, 
    selectedGroupIds, 
    onToggleExpand, 
    onCheck 
}) => {
    const hasChildren = group.children && group.children.length > 0;
    const isExpanded = expandedGroups.has(group.id);
    const isSelected = selectedGroupIds.includes(group.id);

    return (
        <div className="select-none">
            <div
                className="flex items-center p-2 hover:bg-slate-50 rounded"
                style={{ paddingLeft: `${depth * 20 + 8}px` }}
            >
                <div
                    className="mr-2 cursor-pointer"
                    onClick={(e) => { e.stopPropagation(); hasChildren && onToggleExpand(group.id); }}
                >
                    {hasChildren ? (
                        isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />
                    ) : <div className="w-4" />}
                </div>

                <label className="flex items-center cursor-pointer flex-1">
                    <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={e => onCheck(group.id, e.target.checked)}
                        className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 mr-2"
                    />
                    <Folder className="w-4 h-4 text-indigo-200 mr-2 fill-indigo-200" />
                    <span className="text-sm text-slate-700">{group.name}</span>
                </label>
            </div>
            {hasChildren && isExpanded && (
                <div>
                    {group.children!.map(child => (
                        <GroupTreeCheckbox 
                            key={child.id} 
                            group={child} 
                            depth={depth + 1}
                            expandedGroups={expandedGroups}
                            selectedGroupIds={selectedGroupIds}
                            onToggleExpand={onToggleExpand}
                            onCheck={onCheck}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export const HistoryAnalysis: React.FC = () => {
    // State
    const [draftFiles, setDraftFiles] = useState<File[]>([]);
    const [approvedFiles, setApprovedFiles] = useState<File[]>([]);
    const [taskId, setTaskId] = useState<string | null>(null);
    const [task, setTask] = useState<HistoryAnalysisTask | null>(null);
    const [opinions, setOpinions] = useState<InferredOpinion[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedOpinionId, setSelectedOpinionId] = useState<string | null>(null);

    // Rule Groups for "Add to Rule Base"
    const [groups, setGroups] = useState<RuleGroup[]>([]);
    
    // Modal State
    const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
    const [targetOpinionId, setTargetOpinionId] = useState<string | null>(null);
    const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

    // Editing State
    const [editingOpinionId, setEditingOpinionId] = useState<string | null>(null);
    const [editContent, setEditContent] = useState('');
    const [editRisk, setEditRisk] = useState('');

    // Load Rule Groups on mount
    useEffect(() => {
        api.getRuleGroups().then(setGroups).catch(console.error);

        // Restore task from localStorage
        const savedTaskId = localStorage.getItem('ads_history_task_id');
        if (savedTaskId) {
            setTaskId(savedTaskId);
        }
    }, []);

    // Poll Task Status
    useEffect(() => {
        if (!taskId) return;

        const poll = async () => {
            try {
                const data = await api.getHistoryAnalysis(taskId);
                setTask(data.task);
                setOpinions(data.opinions);

                if (data.task.status === 'COMPLETED' || data.task.status === 'FAILED') {
                    setLoading(false);
                } else {
                    setLoading(true);
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        };

        poll(); // Initial call
        const interval = setInterval(poll, 3000); // Poll every 3s

        return () => clearInterval(interval);
    }, [taskId]);

    const handleStartAnalysis = async () => {
        if (draftFiles.length === 0 || approvedFiles.length === 0) {
            setError("请上传原始稿件和修改后稿件");
            return;
        }

        setLoading(true);
        setError(null);
        try {
            const task = await api.startHistoryAnalysis(draftFiles, approvedFiles);
            setTaskId(task.id);
            localStorage.setItem('ads_history_task_id', task.id);
        } catch (e: any) {
            setError(e.message || "启动分析失败");
            setLoading(false);
        }
    };

    const handleReset = () => {
        setTaskId(null);
        setTask(null);
        setOpinions([]);
        setDraftFiles([]);
        setApprovedFiles([]);
        localStorage.removeItem('ads_history_task_id');
    };

    const handleEditStart = (op: InferredOpinion) => {
        setEditingOpinionId(op.id);
        setEditContent(op.opinion);
        setEditRisk(op.risk_level);
    };

    const handleEditSave = async () => {
        if (!editingOpinionId) return;
        try {
            await api.updateOpinion(editingOpinionId, { opinion: editContent, risk_level: editRisk });
            // Optimistic update or wait for poll
            setOpinions(prev => prev.map(op =>
                op.id === editingOpinionId ? { ...op, opinion: editContent, risk_level: editRisk } : op
            ));
            setEditingOpinionId(null);
        } catch (e: any) {
            setError("更新失败: " + e.message);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm("确定要删除这条意见吗？")) return;
        try {
            await api.deleteOpinion(id);
            setOpinions(prev => prev.map(op =>
                op.id === id ? { ...op, status: 'DELETED' } : op
            ));
        } catch (e: any) {
            setError("删除失败: " + e.message);
        }
    };

    const handleAddToRuleClick = (op: InferredOpinion) => {
        setTargetOpinionId(op.id);
        setSelectedGroupIds([]);
        setIsGroupModalOpen(true);
    };

    const toggleExpand = (groupId: string) => {
        const newExpanded = new Set(expandedGroups);
        if (newExpanded.has(groupId)) {
            newExpanded.delete(groupId);
        } else {
            newExpanded.add(groupId);
        }
        setExpandedGroups(newExpanded);
    };

    const handleGroupCheck = (groupId: string, checked: boolean) => {
        if (checked) {
            setSelectedGroupIds(prev => [...prev, groupId]);
        } else {
            setSelectedGroupIds(prev => prev.filter(id => id !== groupId));
        }
    };

    const handleConfirmAddToRule = async () => {
        if (!targetOpinionId || selectedGroupIds.length === 0) {
            alert("请至少选择一个规则组");
            return;
        }
        try {
            await api.convertOpinionToRule(targetOpinionId, selectedGroupIds);
            setOpinions(prev => prev.map(o =>
                o.id === targetOpinionId ? { ...o, status: 'ADDED' } : o
            ));
            setIsGroupModalOpen(false);
            setTargetOpinionId(null);
            setSelectedGroupIds([]);
        } catch (e: any) {
            setError("添加规则失败: " + e.message);
        }
    };

    // Render Helpers
    const renderUpload = () => (
        <div className="max-w-4xl mx-auto space-y-8 mt-8">
            <div className="text-center">
                <h2 className="text-3xl font-bold text-slate-900">历史报告智能分析（测试）</h2>
                <p className="text-slate-500 mt-2">上传原始稿件和修改后稿件pdf，AI将自动提取专家审查意见，暂无法支持超过10m的文件分析，上传前请将文件压缩或分段</p>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
                {/* Draft Upload */}
                <div className="bg-white p-6 rounded-xl border-2 border-dashed border-slate-300 hover:border-indigo-400 transition-colors">
                    <div className="text-center">
                        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
                            <FileText className="w-6 h-6" />
                        </div>
                        <h3 className="font-semibold text-lg mb-2">原始稿件 (修改前)</h3>
                        <input
                            type="file"
                            multiple
                            accept=".pdf,.docx"
                            onChange={e => setDraftFiles(Array.from(e.target.files || []))}
                            className="hidden"
                            id="draft-upload"
                        />
                        <label htmlFor="draft-upload" className="btn-secondary cursor-pointer inline-block px-4 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 text-slate-700 font-medium">
                            选择文件
                        </label>
                        <div className="mt-4 space-y-2">
                            {draftFiles.map((f, i) => (
                                <div key={i} className="text-sm text-slate-600 bg-slate-50 p-2 rounded flex items-center">
                                    <FileText className="w-4 h-4 mr-2" /> {f.name}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Approved Upload */}
                <div className="bg-white p-6 rounded-xl border-2 border-dashed border-slate-300 hover:border-emerald-400 transition-colors">
                    <div className="text-center">
                        <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                            <CheckCircle2 className="w-6 h-6" />
                        </div>
                        <h3 className="font-semibold text-lg mb-2">修改后稿件 (修改后)</h3>
                        <input
                            type="file"
                            multiple
                            accept=".pdf,.docx"
                            onChange={e => setApprovedFiles(Array.from(e.target.files || []))}
                            className="hidden"
                            id="approved-upload"
                        />
                        <label htmlFor="approved-upload" className="btn-secondary cursor-pointer inline-block px-4 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 text-slate-700 font-medium">
                            选择文件
                        </label>
                        <div className="mt-4 space-y-2">
                            {approvedFiles.map((f, i) => (
                                <div key={i} className="text-sm text-slate-600 bg-slate-50 p-2 rounded flex items-center">
                                    <FileText className="w-4 h-4 mr-2" /> {f.name}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <div className="text-center">
                <button
                    onClick={handleStartAnalysis}
                    disabled={loading || draftFiles.length === 0 || approvedFiles.length === 0}
                    className="px-8 py-3 bg-indigo-600 text-white rounded-xl font-bold text-lg hover:bg-indigo-700 disabled:opacity-50 shadow-lg flex items-center mx-auto"
                >
                    {loading ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : <RefreshCw className="w-5 h-5 mr-2" />}
                    开始智能分析
                </button>
            </div>

            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-lg text-center">
                    {error}
                </div>
            )}
        </div>
    );

    const renderWorkspace = () => {
        const activeOpinions = opinions.filter(o => o.status !== 'DELETED');
        const selectedOpinion = opinions.find(o => o.id === selectedOpinionId) || activeOpinions[0];

        // Parse evidence for highlighting
        let draftHighlight = '';
        let approvedHighlight = '';
        if (selectedOpinion?.evidence) {
            const evidence = selectedOpinion.evidence;
            // More robust regex to handle bracket variations and colons
            const draftMatch = evidence.match(/(?:【|\[)修改前(?:】|\])(?:[:：])?\s*([\s\S]*?)(?=(?:【|\[)修改后(?:】|\])|$)/);
            const approvedMatch = evidence.match(/(?:【|\[)修改后(?:】|\])(?:[:：])?\s*([\s\S]*?)$/);
            
            if (draftMatch) draftHighlight = draftMatch[1].trim();
            if (approvedMatch) approvedHighlight = approvedMatch[1].trim();
            
            // Fallback: if regex fails but evidence is short, use it entirely (might be just one sentence)
            if (!approvedHighlight && evidence.length < 100 && !evidence.includes('修改前')) {
                approvedHighlight = evidence.trim();
            }
        }

        const draftFilenames = task?.draft_filenames ? JSON.parse(task.draft_filenames) : [];
        const approvedFilenames = task?.approved_filenames ? JSON.parse(task.approved_filenames) : [];

        return (
            <div className="h-[calc(100vh-100px)] flex flex-col">
                {/* Toolbar */}
                <div className="bg-white border-b border-slate-200 p-4 flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <h2 className="text-xl font-bold text-slate-800">分析结果</h2>
                        <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium">
                            共发现 {activeOpinions.length} 条意见
                        </span>
                        {loading && <span className="text-sm text-slate-500 flex items-center"><Loader2 className="w-4 h-4 mr-1 animate-spin" /> 分析中...</span>}
                    </div>
                    <div className="flex items-center gap-4">
                        <button onClick={handleReset} className="text-slate-500 hover:text-slate-700 text-sm">
                            重新开始
                        </button>
                    </div>
                </div>

                {/* Main Split View */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Left: Opinions List */}
                    <div className="w-1/2 border-r border-slate-200 overflow-y-auto bg-slate-50 p-4 space-y-4">
                        {activeOpinions.map(op => {
                            const RISK_LEVELS = ['高风险', '中风险', '低风险'];
                            const REVIEW_TYPES = ['内容完整性', '计算结果准确性', '禁止条款', '前后逻辑一致性', '措施遵从性', '计算正确性'];

                            return (
                                <div
                                    key={op.id}
                                    onClick={() => setSelectedOpinionId(op.id)}
                                    className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${selectedOpinion?.id === op.id ? 'border-indigo-600 bg-white shadow-md' : 'border-transparent bg-white hover:border-indigo-200'
                                        } ${op.status === 'ADDED' ? 'opacity-75 bg-emerald-50' : ''}`}
                                >
                                    {/* Header with Dropdowns and Add Button */}
                                    <div className="flex items-center gap-2 mb-3" onClick={e => e.stopPropagation()}>
                                        {/* Risk Level Dropdown */}
                                        <select
                                            value={op.risk_level}
                                            onChange={async (e) => {
                                                const newRisk = e.target.value;
                                                try {
                                                    await api.updateOpinion(op.id, { risk_level: newRisk });
                                                    setOpinions(prev => prev.map(o =>
                                                        o.id === op.id ? { ...o, risk_level: newRisk } : o
                                                    ));
                                                } catch (err: any) {
                                                    setError("更新失败: " + err.message);
                                                }
                                            }}
                                            className="text-xs px-2 py-1 border border-slate-300 rounded font-medium focus:ring-2 focus:ring-indigo-500"
                                            disabled={op.status === 'ADDED'}
                                        >
                                            {RISK_LEVELS.map(level => (
                                                <option key={level} value={level}>{level}</option>
                                            ))}
                                        </select>

                                        {/* Review Type Dropdown */}
                                        <select
                                            value={op.review_type || '内容完整性'}
                                            onChange={async (e) => {
                                                const newType = e.target.value;
                                                try {
                                                    await api.updateOpinion(op.id, { review_type: newType });
                                                    setOpinions(prev => prev.map(o =>
                                                        o.id === op.id ? { ...o, review_type: newType } : o
                                                    ));
                                                } catch (err: any) {
                                                    setError("更新失败: " + err.message);
                                                }
                                            }}
                                            className="flex-1 text-xs px-2 py-1 border border-slate-300 rounded font-medium focus:ring-2 focus:ring-indigo-500"
                                            disabled={op.status === 'ADDED'}
                                        >
                                            {REVIEW_TYPES.map(type => (
                                                <option key={type} value={type}>{type}</option>
                                            ))}
                                        </select>

                                        {/* Add to Rule Button */}
                                        {op.status === 'ADDED' ? (
                                            <span className="text-xs font-bold text-emerald-600 flex items-center whitespace-nowrap">
                                                <CheckCircle2 className="w-3 h-3 mr-1" /> 已添加
                                            </span>
                                        ) : (
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleAddToRuleClick(op); }}
                                                className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-semibold hover:bg-indigo-700 transition-colors whitespace-nowrap"
                                            >
                                                添加到规则库
                                            </button>
                                        )}
                                    </div>

                                    {/* Opinion Content */}
                                    {editingOpinionId === op.id ? (
                                        <div className="space-y-2" onClick={e => e.stopPropagation()}>
                                            <textarea
                                                value={editContent}
                                                onChange={e => setEditContent(e.target.value)}
                                                className="w-full p-2 border rounded text-sm h-24"
                                            />
                                            <div className="flex justify-end gap-2">
                                                <button onClick={() => setEditingOpinionId(null)} className="text-xs text-slate-500">取消</button>
                                                <button onClick={handleEditSave} className="text-xs bg-indigo-600 text-white px-3 py-1 rounded">保存</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-800 font-medium text-sm leading-relaxed">
                                            {op.opinion}
                                        </p>
                                    )}

                                    {/* Action Buttons */}
                                    {op.status !== 'ADDED' && editingOpinionId !== op.id && (
                                        <div className="flex gap-2 mt-3 pt-3 border-t border-slate-100">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleEditStart(op); }}
                                                className="text-xs text-slate-600 hover:text-indigo-600 flex items-center gap-1"
                                            >
                                                <Edit2 className="w-3 h-3" /> 编辑
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleDelete(op.id); }}
                                                className="text-xs text-slate-600 hover:text-red-600 flex items-center gap-1"
                                            >
                                                <Trash2 className="w-3 h-3" /> 删除
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )
                        })}

                        {activeOpinions.length === 0 && !loading && (
                            <div className="text-center text-slate-500 mt-10">
                                未发现任何审查意见
                            </div>
                        )}
                    </div>

                    {/* Right: Document Viewers */}
                    <div className="w-1/2 bg-slate-100 flex flex-col overflow-hidden">
                        {selectedOpinion && task ? (
                            <div className="flex-1 flex flex-col">
                                {/* Modified Document Viewer (Full Height) */}
                                <div className="h-full">
                                    <DocumentViewer
                                        taskId={task.id}
                                        fileType="approved"
                                        fileIndex={0}
                                        filename={approvedFilenames[0] || 'unknown.pdf'}
                                        locationJson={selectedOpinion.approved_file_location}
                                        title="修改后稿件（修改后）"
                                        highlightText={approvedHighlight}
                                    />
                                </div>
                            </div>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-400">
                                <p>请在左侧选择一条意见查看文档对比</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Group Selection Modal */}
                {isGroupModalOpen && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl p-6 w-[500px] max-h-[80vh] flex flex-col shadow-2xl">
                            <h3 className="text-lg font-bold mb-4">选择目标规则组</h3>
                            <div className="flex-1 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
                                {groups.map(g => (
                                    <GroupTreeCheckbox
                                        key={g.id}
                                        group={g}
                                        expandedGroups={expandedGroups}
                                        selectedGroupIds={selectedGroupIds}
                                        onToggleExpand={toggleExpand}
                                        onCheck={handleGroupCheck}
                                    />
                                ))}
                            </div>
                            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                                <button
                                    onClick={() => setIsGroupModalOpen(false)}
                                    className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg text-sm font-medium"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleConfirmAddToRule}
                                    disabled={selectedGroupIds.length === 0}
                                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
                                >
                                    确认添加
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-slate-50">
            {!taskId ? renderUpload() : renderWorkspace()}
        </div>
    );
};
