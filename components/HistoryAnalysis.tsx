import React, { useState, useEffect, useRef } from 'react';
import { HistoryAnalysisTask, InferredOpinion, RuleGroup } from '../types';
import { api } from '../services/api';
import { FileUp, Loader2, AlertCircle, CheckCircle2, XCircle, ArrowRight, Save, Trash2, Edit2, FileText, RefreshCw } from 'lucide-react';
import { DocumentViewer } from './DocumentViewer';

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
    const [selectedGroupId, setSelectedGroupId] = useState<string>('');

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

        if (!selectedGroupId) {
            setError("请选择目标规则组");
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
        setSelectedGroupId('');
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

    const handleAddToRule = async (op: InferredOpinion) => {
        if (!selectedGroupId) {
            alert("请先选择目标规则组");
            return;
        }
        try {
            await api.convertOpinionToRule(op.id, selectedGroupId);
            setOpinions(prev => prev.map(o =>
                o.id === op.id ? { ...o, status: 'ADDED' } : o
            ));
        } catch (e: any) {
            setError("添加规则失败: " + e.message);
        }
    };

    // Render Helpers
    const renderUpload = () => (
        <div className="max-w-4xl mx-auto space-y-8 mt-8">
            <div className="text-center">
                <h2 className="text-3xl font-bold text-slate-900">历史报告智能分析</h2>
                <p className="text-slate-500 mt-2">上传原始稿件和修改后稿件，AI将自动提取专家审查意见</p>
            </div>

            {/* Rule Group Selection - Now at the top */}
            <div className="bg-white p-6 rounded-xl border-2 border-indigo-200 shadow-sm">
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                    选择目标规则组 <span className="text-red-500">*</span>
                </label>
                <select
                    value={selectedGroupId}
                    onChange={e => setSelectedGroupId(e.target.value)}
                    className="w-full p-3 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                    <option value="">-- 请选择规则组 --</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
                <p className="text-xs text-slate-500 mt-2">提取的审查意见将被添加到此规则组</p>
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
                    disabled={loading || draftFiles.length === 0 || approvedFiles.length === 0 || !selectedGroupId}
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
        const selectedGroup = groups.find(g => g.id === selectedGroupId);

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
                        {selectedGroup && (
                            <div className="text-sm">
                                <span className="text-slate-500">目标规则组：</span>
                                <span className="font-semibold text-slate-800">{selectedGroup.name}</span>
                            </div>
                        )}
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
                                                onClick={(e) => { e.stopPropagation(); handleAddToRule(op); }}
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
                                {/* Original Document Viewer (Top) */}
                                <div className="h-1/2 border-b-2 border-slate-300">
                                    <DocumentViewer
                                        taskId={task.id}
                                        fileType="draft"
                                        fileIndex={0}
                                        location={selectedOpinion.draft_file_location ? JSON.parse(selectedOpinion.draft_file_location) : null}
                                        title="原始稿件（修改前）"
                                    />
                                </div>

                                {/* Modified Document Viewer (Bottom) */}
                                <div className="h-1/2">
                                    <DocumentViewer
                                        taskId={task.id}
                                        fileType="approved"
                                        fileIndex={0}
                                        location={selectedOpinion.approved_file_location ? JSON.parse(selectedOpinion.approved_file_location) : null}
                                        title="修改后稿件（修改后）"
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
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-slate-50">
            {!taskId ? renderUpload() : renderWorkspace()}
        </div>
    );
};
