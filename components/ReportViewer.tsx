import React, { useEffect, useState } from 'react';
import { ReviewResult, ReviewTask, ResultCode } from '../types';
import { api } from '../services/api';
import { CheckCircle2, XCircle, AlertCircle, Download, RefreshCw, ChevronDown, ChevronUp, ArrowLeft, FileText, Loader2, Trash2, Edit3, FileDown, X, Save, Filter, Shield } from 'lucide-react';
import { downloadCSV } from '../services/fileUtils';

type FilterStatus = 'ALL' | ResultCode;

export const ReportViewer: React.FC = () => {
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<ReviewTask | null>(null);
  const [results, setResults] = useState<ReviewResult[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('ALL');
  const [filterSource, setFilterSource] = useState<string>('ALL');
  const [editingResult, setEditingResult] = useState<ReviewResult | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadTasks();
  }, []);

  useEffect(() => {
    if (selectedTaskId) {
      setLoading(true);
      Promise.all([
        api.getReviewTask(selectedTaskId),
        api.getResults(selectedTaskId)
      ])
        .then(([task, res]) => {
          setSelectedTask(task);
          setResults(res);
        })
        .catch(e => console.error(e))
        .finally(() => setLoading(false));
    }
  }, [selectedTaskId]);

  const loadTasks = async () => {
    try {
      const data = await api.getReviewTasks();
      setTasks(data.reverse());
    } catch (e) {
      console.error(e);
    }
  };

  const handleExportCSV = () => {
    const csvContent = [
        "条款号,规范来源,规则内容,结果,重要性,判断理由,引用证据,修改建议",
        ...filteredResults.map(r =>
          `"${r.clause_number || ''}","${(r.standard_name || '').replace(/"/g, '""')}","${(r.rule_content || '').replace(/"/g, '""')}","${r.result_code}","${r.importance || ''}","${(r.reasoning || '').replace(/"/g, '""')}","${(r.evidence || '').replace(/"/g, '""')}","${(r.suggestion || '').replace(/"/g, '""')}"`
        )
    ].join('\n');
    downloadCSV(csvContent, `review_${selectedTaskId?.substring(0,8)}.csv`);
  };

  const handleDownloadPdf = async () => {
    if (!selectedTaskId) return;
    setPdfLoading(true);
    try {
      await api.downloadSummaryPdf(selectedTaskId);
    } catch (e: any) {
      alert(e.message || 'Failed to generate PDF');
    } finally {
      setPdfLoading(false);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await api.deleteReviewTask(taskId);
      setTasks(tasks.filter(t => t.id !== taskId));
      setDeleteConfirm(null);
    } catch (e: any) {
      alert(e.message || 'Failed to delete task');
    }
  };

  const handleDeleteResult = async (resultId: string) => {
    try {
      await api.deleteResult(resultId);
      setResults(results.filter(r => r.id !== resultId));
      setDeleteConfirm(null);
    } catch (e: any) {
      alert(e.message || 'Failed to delete result');
    }
  };

  const handleUpdateResult = async () => {
    if (!editingResult) return;
    try {
      const updated = await api.updateResult(editingResult.id, {
        result_code: editingResult.result_code,
        reasoning: editingResult.reasoning || undefined,
        evidence: editingResult.evidence || undefined,
        suggestion: editingResult.suggestion || undefined
      });
      setResults(results.map(r => r.id === updated.id ? { ...r, ...updated } : r));
      setEditingResult(null);
    } catch (e: any) {
      alert(e.message || 'Failed to update result');
    }
  };

  const getResultBadge = (code: string) => {
    switch (code) {
      case 'PASS':
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200"><CheckCircle2 className="w-3 h-3 mr-1"/> 通过</span>;
      case 'REJECT':
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-red-100 text-red-800 text-xs font-bold border border-red-200"><XCircle className="w-3 h-3 mr-1"/> 不通过</span>;
      case 'MANUAL_CHECK':
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-bold border border-orange-200"><AlertCircle className="w-3 h-3 mr-1"/> 待复核</span>;
      default:
        return <span className="inline-flex items-center px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">{code}</span>;
    }
  };

  const getImportanceBadge = (importance?: string) => {
    switch (importance) {
      case '重要':
        return <span className="px-2 py-0.5 rounded text-xs bg-red-50 text-red-700 border border-red-200">重要</span>;
      case '中等':
        return <span className="px-2 py-0.5 rounded text-xs bg-amber-50 text-amber-700 border border-amber-200">中等</span>;
      case '一般':
        return <span className="px-2 py-0.5 rounded text-xs bg-slate-50 text-slate-600 border border-slate-200">一般</span>;
      default:
        return null;
    }
  };

  // Get unique sources for filter
  const uniqueSources = React.useMemo(() => {
    const sources = new Set<string>();
    results.forEach(r => {
      if (r.standard_name) sources.add(r.standard_name);
    });
    return Array.from(sources).sort();
  }, [results]);

  const filteredResults = results.filter(r => {
    const statusMatch = filterStatus === 'ALL' || r.result_code === filterStatus;
    const sourceMatch = filterSource === 'ALL' || r.standard_name === filterSource;
    return statusMatch && sourceMatch;
  });

  const stats = {
    PASS: results.filter(r => r.result_code === 'PASS').length,
    REJECT: results.filter(r => r.result_code === 'REJECT').length,
    MANUAL_CHECK: results.filter(r => r.result_code === 'MANUAL_CHECK').length
  };

  // List View
  if (!selectedTaskId) {
    return (
      <div className="space-y-6">
         <div className="flex justify-between items-end border-b border-slate-200 pb-4">
           <div>
              <h2 className="text-2xl font-bold text-slate-900">审查历史</h2>
              <p className="text-slate-500 mt-1">选择已完成的审查任务查看合规报告</p>
           </div>
           <button onClick={loadTasks} className="text-indigo-600 hover:bg-indigo-50 p-2 rounded-lg"><RefreshCw className="w-4 h-4"/></button>
         </div>

         <div className="grid gap-4">
            {tasks.length === 0 && (
                <div className="text-center py-12 text-slate-400 bg-white rounded-xl border border-dashed border-slate-200">
                    <p>暂无审查记录</p>
                </div>
            )}
            {tasks.map(task => (
                <div
                    key={task.id}
                    className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all flex justify-between items-center group"
                >
                    <div className="flex items-center gap-4 flex-1 cursor-pointer" onClick={() => setSelectedTaskId(task.id)}>
                        <div className={`p-3 rounded-full ${task.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-600' : task.status === 'FAILED' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'}`}>
                           {task.status === 'COMPLETED' ? <CheckCircle2 className="w-5 h-5"/> : task.status === 'FAILED' ? <XCircle className="w-5 h-5"/> : <Loader2 className="w-5 h-5 animate-spin"/>}
                        </div>
                        <div className="flex-1">
                            <div className="font-semibold text-slate-900">{task.document_name || `文档 ${task.document_id.substring(0,8)}...`}</div>
                            <div className="text-xs text-slate-500 flex items-center gap-2 mt-1 flex-wrap">
                                <span className="flex items-center"><Shield className="w-3 h-3 mr-1"/> {task.rule_group_name || `规则组 ${task.rule_group_id.substring(0,6)}...`}</span>
                                {task.stats && (
                                  <>
                                    <span className="w-1 h-1 bg-slate-300 rounded-full"></span>
                                    <span className="text-emerald-600">✓{task.stats.PASS}</span>
                                    <span className="text-red-600">✗{task.stats.REJECT}</span>
                                    <span className="text-orange-600">?{task.stats.MANUAL_CHECK}</span>
                                  </>
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {deleteConfirm === task.id ? (
                        <>
                          <button onClick={() => handleDeleteTask(task.id)} className="px-3 py-1 bg-red-600 text-white rounded text-sm">确认删除</button>
                          <button onClick={() => setDeleteConfirm(null)} className="px-3 py-1 bg-slate-200 text-slate-700 rounded text-sm">取消</button>
                        </>
                      ) : (
                        <button onClick={() => setDeleteConfirm(task.id)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all">
                          <Trash2 className="w-4 h-4"/>
                        </button>
                      )}
                      <div onClick={() => setSelectedTaskId(task.id)} className="text-indigo-600 opacity-0 group-hover:opacity-100 font-medium text-sm transition-opacity cursor-pointer px-2">
                          查看 &rarr;
                      </div>
                    </div>
                </div>
            ))}
         </div>
      </div>
    );
  }

  // Detail View
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <button onClick={() => { setSelectedTaskId(null); setSelectedTask(null); setFilterStatus('ALL'); setFilterSource('ALL'); }} className="flex items-center text-slate-500 hover:text-slate-900 transition-colors">
            <ArrowLeft className="w-4 h-4 mr-1"/> 返回列表
        </button>
        <div className="flex gap-2 flex-wrap">
            <button onClick={handleExportCSV} className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center shadow-sm font-medium">
                <Download className="w-4 h-4 mr-2"/> 导出CSV
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={pdfLoading || selectedTask?.status !== 'COMPLETED'}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center shadow-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {pdfLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin"/> : <FileDown className="w-4 h-4 mr-2"/>}
                生成摘要PDF
            </button>
        </div>
      </div>

      {/* Task Info & Stats */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-slate-900">{selectedTask?.document_name || '审查详情'}</h2>
              <p className="text-sm text-slate-500 mt-1">
                规则组: {selectedTask?.rule_group_name || selectedTask?.rule_group_id} |
                任务ID: {selectedTaskId?.substring(0,8)}...
              </p>
            </div>
            <div className="flex gap-3">
              <div className="text-center px-4 py-2 bg-emerald-50 rounded-lg border border-emerald-200">
                <div className="text-2xl font-bold text-emerald-600">{stats.PASS}</div>
                <div className="text-xs text-emerald-700">通过</div>
              </div>
              <div className="text-center px-4 py-2 bg-red-50 rounded-lg border border-red-200">
                <div className="text-2xl font-bold text-red-600">{stats.REJECT}</div>
                <div className="text-xs text-red-700">不通过</div>
              </div>
              <div className="text-center px-4 py-2 bg-orange-50 rounded-lg border border-orange-200">
                <div className="text-2xl font-bold text-orange-600">{stats.MANUAL_CHECK}</div>
                <div className="text-xs text-orange-700">待复核</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center gap-4">
          <Filter className="w-4 h-4 text-slate-400"/>
          <span className="text-sm text-slate-600">结果:</span>
          <div className="flex gap-2">
            {(['ALL', 'PASS', 'REJECT', 'MANUAL_CHECK'] as FilterStatus[]).map(status => (
              <button
                key={status}
                onClick={() => setFilterStatus(status)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  filterStatus === status
                    ? status === 'PASS' ? 'bg-emerald-600 text-white'
                      : status === 'REJECT' ? 'bg-red-600 text-white'
                      : status === 'MANUAL_CHECK' ? 'bg-orange-600 text-white'
                      : 'bg-indigo-600 text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                {status === 'ALL' ? '全部' : status === 'PASS' ? '通过' : status === 'REJECT' ? '不通过' : '待复核'}
                {status !== 'ALL' && ` (${stats[status]})`}
              </button>
            ))}
          </div>
          {uniqueSources.length > 1 && (
            <>
              <span className="text-slate-300">|</span>
              <span className="text-sm text-slate-600">规范来源:</span>
              <select
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
                className="px-3 py-1 rounded-lg text-xs font-medium bg-white text-slate-600 border border-slate-200 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-300 max-w-[200px]"
              >
                <option value="ALL">全部来源 ({results.length})</option>
                {uniqueSources.map(source => (
                  <option key={source} value={source}>
                    {source.length > 25 ? source.substring(0, 25) + '...' : source} ({results.filter(r => r.standard_name === source).length})
                  </option>
                ))}
              </select>
            </>
          )}
          {(filterStatus !== 'ALL' || filterSource !== 'ALL') && (
            <span className="text-xs text-slate-500">
              显示 {filteredResults.length} / {results.length} 条
            </span>
          )}
        </div>

        {loading ? (
             <div className="p-12 text-center text-slate-500 flex justify-center items-center">
                 <Loader2 className="w-6 h-6 animate-spin mr-2" /> 加载中...
             </div>
        ) : (
            <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                        <th className="px-4 py-3 font-semibold text-slate-700 w-24">条款号</th>
                        <th className="px-4 py-3 font-semibold text-slate-700 w-40">规范来源</th>
                        <th className="px-4 py-3 font-semibold text-slate-700 w-28">结果</th>
                        <th className="px-4 py-3 font-semibold text-slate-700 w-20">重要性</th>
                        <th className="px-4 py-3 font-semibold text-slate-700">规则内容 / 判断理由</th>
                        <th className="px-4 py-3 font-semibold text-slate-700 w-24">操作</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                    {filteredResults.map(r => (
                        <React.Fragment key={r.id}>
                            <tr
                              className={`hover:bg-slate-50 transition-colors ${
                                r.result_code === 'PASS' ? 'bg-emerald-50/30'
                                : r.result_code === 'REJECT' ? 'bg-red-50/30'
                                : r.result_code === 'MANUAL_CHECK' ? 'bg-orange-50/30'
                                : ''
                              }`}
                            >
                                <td className="px-4 py-3 font-mono text-sm text-slate-700">{r.clause_number || 'N/A'}</td>
                                <td className="px-4 py-3 text-xs text-slate-600 max-w-[160px]">
                                    <div className="line-clamp-2" title={r.standard_name || ''}>{r.standard_name || '-'}</div>
                                </td>
                                <td className="px-4 py-3">{getResultBadge(r.result_code)}</td>
                                <td className="px-4 py-3">{getImportanceBadge(r.importance)}</td>
                                <td className="px-4 py-3">
                                    <div className="text-slate-800 font-medium mb-1 line-clamp-1">{r.rule_content || 'N/A'}</div>
                                    <div className="line-clamp-2 text-slate-500 text-xs">{r.reasoning || '无判断理由'}</div>
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-1">
                                    <button
                                      onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                                      className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                                    >
                                      {expandedId === r.id ? <ChevronUp className="w-4 h-4"/> : <ChevronDown className="w-4 h-4"/>}
                                    </button>
                                    <button
                                      onClick={() => setEditingResult(r)}
                                      className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                                    >
                                      <Edit3 className="w-4 h-4"/>
                                    </button>
                                    {deleteConfirm === r.id ? (
                                      <div className="flex gap-1">
                                        <button onClick={() => handleDeleteResult(r.id)} className="p-1 bg-red-600 text-white rounded text-xs">确认</button>
                                        <button onClick={() => setDeleteConfirm(null)} className="p-1 bg-slate-300 text-slate-700 rounded text-xs">取消</button>
                                      </div>
                                    ) : (
                                      <button
                                        onClick={() => setDeleteConfirm(r.id)}
                                        className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded"
                                      >
                                        <Trash2 className="w-4 h-4"/>
                                      </button>
                                    )}
                                  </div>
                                </td>
                            </tr>
                            {expandedId === r.id && (
                                <tr className="bg-slate-50/80">
                                    <td colSpan={6} className="px-4 pb-4 pt-2">
                                        <div className="grid md:grid-cols-3 gap-4">
                                            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                                                <div className="text-xs font-bold text-slate-400 uppercase mb-2">判断理由</div>
                                                <div className="text-slate-700 text-sm leading-relaxed">{r.reasoning || '无'}</div>
                                            </div>
                                            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                                                <div className="text-xs font-bold text-slate-400 uppercase mb-2">引用证据</div>
                                                <div className="italic text-slate-600 text-sm bg-slate-50 p-2 rounded border border-slate-100">"{r.evidence || '无'}"</div>
                                            </div>
                                            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                                                <div className="text-xs font-bold text-slate-400 uppercase mb-2">修改建议</div>
                                                <div className="text-slate-700 text-sm leading-relaxed">{r.suggestion || '无'}</div>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </React.Fragment>
                    ))}
                    {filteredResults.length === 0 && (
                        <tr><td colSpan={6} className="text-center p-8 text-slate-400">
                          {results.length === 0 ? '暂无审查结果' : '没有符合筛选条件的结果'}
                        </td></tr>
                    )}
                </tbody>
            </table>
        )}
      </div>

      {/* Edit Modal */}
      {editingResult && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-lg font-bold text-slate-900">编辑审查结果</h3>
              <button onClick={() => setEditingResult(null)} className="p-2 hover:bg-slate-100 rounded-lg">
                <X className="w-5 h-5 text-slate-500"/>
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">条款号</label>
                <input type="text" value={editingResult.clause_number || ''} disabled className="w-full px-3 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-500"/>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">审查结果</label>
                <select
                  value={editingResult.result_code}
                  onChange={e => setEditingResult({...editingResult, result_code: e.target.value as ResultCode})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  <option value="PASS">通过 (PASS)</option>
                  <option value="REJECT">不通过 (REJECT)</option>
                  <option value="MANUAL_CHECK">待复核 (MANUAL_CHECK)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">判断理由</label>
                <textarea
                  value={editingResult.reasoning || ''}
                  onChange={e => setEditingResult({...editingResult, reasoning: e.target.value})}
                  rows={3}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">引用证据</label>
                <textarea
                  value={editingResult.evidence || ''}
                  onChange={e => setEditingResult({...editingResult, evidence: e.target.value})}
                  rows={3}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">修改建议</label>
                <textarea
                  value={editingResult.suggestion || ''}
                  onChange={e => setEditingResult({...editingResult, suggestion: e.target.value})}
                  rows={3}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>
            <div className="p-6 border-t border-slate-200 flex justify-end gap-3">
              <button onClick={() => setEditingResult(null)} className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">
                取消
              </button>
              <button onClick={handleUpdateResult} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center">
                <Save className="w-4 h-4 mr-2"/> 保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};