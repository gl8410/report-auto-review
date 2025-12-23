import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { Document, RuleGroup } from '../types';
import { Loader2, Play, CheckCircle2, AlertCircle, FileText, Shield, XCircle, Clock, BarChart3, RefreshCw, CheckSquare, Square } from 'lucide-react';

interface ReviewEngineProps {
  onGoToReports: () => void;
}

interface TaskDetails {
  id: string;
  document_name: string;
  rule_group_name: string;
  rule_group_names?: string;
  status: string;
  progress: number;
  results_count: number;
  stats: {
    PASS: number;
    REJECT: number;
    MANUAL_CHECK: number;
  };
}

const STORAGE_KEY = 'ads_active_review_task';

export const ReviewEngine: React.FC<ReviewEngineProps> = ({ onGoToReports }) => {
  // Selection State
  const [docs, setDocs] = useState<Document[]>([]);
  const [groups, setGroups] = useState<RuleGroup[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);

  // Execution State
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [taskDetails, setTaskDetails] = useState<TaskDetails | null>(null);
  const [totalRules, setTotalRules] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [restoringTask, setRestoringTask] = useState(true);

  const loadResources = useCallback(async () => {
    try {
      const [docsData, groupsData] = await Promise.all([
        api.getDocuments(),
        api.getRuleGroups()
      ]);
      setDocs(docsData);
      setGroups(groupsData);
    } catch (e) {
      console.error("Failed to load resources", e);
    }
  }, []);

  // Restore active task from localStorage on mount
  useEffect(() => {
    const restoreTask = async () => {
      try {
        const savedTaskId = localStorage.getItem(STORAGE_KEY);
        if (savedTaskId) {
          // Verify the task still exists and is in progress
          const task = await api.getReviewTask(savedTaskId);
          if (task && (task.status === 'PROCESSING' || task.status === 'PENDING')) {
            setActiveTaskId(savedTaskId);
            setTaskDetails(task);
            // Estimate total rules from results if available
            if (task.progress > 0 && task.results_count > 0) {
              setTotalRules(Math.round(task.results_count * 100 / task.progress));
            }
          } else if (task && task.status === 'COMPLETED') {
            // Show completed task
            setActiveTaskId(savedTaskId);
            setTaskDetails(task);
            setTotalRules(task.results_count);
          } else {
            // Task finished or doesn't exist, clear storage
            localStorage.removeItem(STORAGE_KEY);
          }
        }
      } catch (e) {
        console.error("Failed to restore task", e);
        localStorage.removeItem(STORAGE_KEY);
      } finally {
        setRestoringTask(false);
      }
    };
    restoreTask();
  }, []);

  useEffect(() => {
    loadResources();
  }, [loadResources]);

  useEffect(() => {
    if (!activeTaskId) return;

    const interval = setInterval(async () => {
      try {
        const task = await api.getReviewTask(activeTaskId);
        setTaskDetails(task);

        if (task.status === 'COMPLETED' || task.status === 'FAILED') {
          clearInterval(interval);
          // Keep in localStorage for completed tasks so user can see results
          // Will be cleared when they click "开始新审查"
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [activeTaskId]);

  const startReview = async () => {
    if (!selectedDocId || selectedGroupIds.length === 0) return;
    setError(null);
    setLoading(true);
    setTaskDetails(null);

    try {
      const result = await api.startReview(selectedDocId, selectedGroupIds);
      setActiveTaskId(result.task_id);
      setTotalRules(result.total_rules);
      // Save to localStorage so we can restore if user navigates away
      localStorage.setItem(STORAGE_KEY, result.task_id);
    } catch (e: any) {
      setError("启动审查任务失败: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const resetReview = () => {
    setActiveTaskId(null);
    setTaskDetails(null);
    setSelectedDocId('');
    setSelectedGroupIds([]);
    setTotalRules(0);
    setError(null);
    // Clear from localStorage
    localStorage.removeItem(STORAGE_KEY);
  };

  const terminateReview = async () => {
    if (!activeTaskId) return;
    try {
      await api.cancelReviewTask(activeTaskId);
      // Force immediate status update
      const task = await api.getReviewTask(activeTaskId);
      setTaskDetails(task);
    } catch (e: any) {
      setError("终止任务失败: " + e.message);
    }
  };

  const toggleGroupSelection = (groupId: string) => {
    setSelectedGroupIds(prev => {
      if (prev.includes(groupId)) {
        return prev.filter(id => id !== groupId);
      } else {
        return [...prev, groupId];
      }
    });
  };

  // Helper to flatten groups for list view
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

  const flatGroups = flattenGroups(groups);

  // Show loading while checking for active task on mount
  if (restoringTask) {
    return (
      <div className="max-w-2xl mx-auto mt-16 text-center bg-white p-8 rounded-xl shadow-lg border border-slate-200">
        <Loader2 className="w-12 h-12 mx-auto mb-4 animate-spin text-indigo-600" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">正在检查审查任务...</h2>
      </div>
    );
  }

  if (activeTaskId && taskDetails) {
    const { status, progress, stats, document_name, rule_group_name, rule_group_names, results_count } = taskDetails;
    const isCompleted = status === 'COMPLETED';
    const isFailed = status === 'FAILED';
    const isCancelled = status === 'CANCELLED';

    // Display combined names if available, otherwise fallback to single name
    const displayGroupName = rule_group_names || rule_group_name;

    return (
      <div className="max-w-3xl mx-auto mt-8 bg-white p-8 rounded-xl shadow-lg border border-slate-200">
        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-slate-900 mb-2">
            {isCompleted ? '✅ 审查完成' : isFailed ? '❌ 审查失败' : isCancelled ? '🛑 审查已终止' : '🔍 审查进行中'}
          </h2>
          <p className="text-slate-500">
            {isCompleted ? '所有规则已审查完毕' : isFailed ? '审查过程中出现错误' : isCancelled ? '用户手动终止了审查' : 'AI正在逐条审查规则...'}
          </p>
        </div>

        {/* Task Info */}
        <div className="bg-slate-50 rounded-lg p-4 mb-6 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-slate-500">文档：</span>
              <span className="font-medium text-slate-800">{document_name}</span>
            </div>
            <div>
              <span className="text-slate-500">规则组：</span>
              <span className="font-medium text-slate-800" title={displayGroupName}>{displayGroupName}</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex mb-2 items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full ${isCompleted ? 'text-emerald-600 bg-emerald-50' :
                isFailed ? 'text-red-600 bg-red-50' :
                  isCancelled ? 'text-slate-600 bg-slate-50' :
                    'text-indigo-600 bg-indigo-50'
                }`}>
                {status === 'PROCESSING' ? '处理中' : status === 'PENDING' ? '等待中' : status === 'COMPLETED' ? '已完成' : status === 'CANCELLED' ? '已终止' : '失败'}
              </span>
              {!isCompleted && !isFailed && !isCancelled && (
                <span className="text-xs text-slate-500">
                  已审查 {results_count} / {totalRules} 条规则
                </span>
              )}
            </div>
            <span className="text-sm font-semibold text-indigo-600">{progress}%</span>
          </div>
          <div className="overflow-hidden h-3 rounded-full bg-slate-100">
            <div
              style={{ width: `${progress}%` }}
              className={`h-full transition-all duration-500 ease-out ${isCompleted ? 'bg-emerald-500' : isFailed ? 'bg-red-500' : isCancelled ? 'bg-slate-400' : 'bg-indigo-600'
                }`}
            />
          </div>
        </div>

        {/* Real-time Stats */}
        {(status === 'PROCESSING' || isCompleted || isCancelled) && stats && (
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-emerald-50 rounded-lg p-4 text-center">
              <div className="flex items-center justify-center gap-1 text-emerald-600 mb-1">
                <CheckCircle2 className="w-5 h-5" />
                <span className="text-2xl font-bold">{stats.PASS}</span>
              </div>
              <span className="text-xs text-emerald-600">通过</span>
            </div>
            <div className="bg-red-50 rounded-lg p-4 text-center">
              <div className="flex items-center justify-center gap-1 text-red-600 mb-1">
                <XCircle className="w-5 h-5" />
                <span className="text-2xl font-bold">{stats.REJECT}</span>
              </div>
              <span className="text-xs text-red-600">不通过</span>
            </div>
            <div className="bg-amber-50 rounded-lg p-4 text-center">
              <div className="flex items-center justify-center gap-1 text-amber-600 mb-1">
                <Clock className="w-5 h-5" />
                <span className="text-2xl font-bold">{stats.MANUAL_CHECK}</span>
              </div>
              <span className="text-xs text-amber-600">待人工复核</span>
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {!isCompleted && !isFailed && !isCancelled && (
          <div className="flex justify-center items-center text-slate-400 text-sm py-4">
            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            正在审查中，每条规则约需10-30秒...
          </div>
        )}

        {/* Terminate Button */}
        {!isCompleted && !isFailed && !isCancelled && (
          <div className="flex justify-center pt-4 border-t border-slate-100">
            <button
              onClick={terminateReview}
              className="px-4 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg flex items-center gap-2 transition-colors"
            >
              <XCircle className="w-4 h-4" />
              终止审查
            </button>
          </div>
        )}

        {/* Action Buttons */}
        {(isCompleted || isFailed || isCancelled) && (
          <div className="flex justify-center gap-4 pt-4 border-t border-slate-100">
            <button
              onClick={resetReview}
              className="px-4 py-2 text-slate-600 hover:text-slate-900 flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              开始新审查
            </button>
            {isCompleted && (
              <button
                onClick={onGoToReports}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm flex items-center gap-2"
              >
                <BarChart3 className="w-4 h-4" />
                查看详细报告
              </button>
            )}
          </div>
        )}

        {error && (
          <div className="text-red-600 bg-red-50 p-4 rounded-lg flex items-center justify-center gap-2 mt-4">
            <AlertCircle className="w-5 h-5" /> {error}
          </div>
        )}
      </div>
    );
  }

  // Show loading state while waiting for first poll
  if (activeTaskId && !taskDetails) {
    return (
      <div className="max-w-2xl mx-auto mt-16 text-center bg-white p-8 rounded-xl shadow-lg border border-slate-200">
        <Loader2 className="w-12 h-12 mx-auto mb-4 animate-spin text-indigo-600" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">正在启动审查任务...</h2>
        <p className="text-slate-500">共 {totalRules} 条规则待审查</p>
      </div>
    );
  }

  // Selection View
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-slate-900">审查中心</h2>
        <p className="text-slate-500 mt-2">选择文档和规则组，启动自动化审查任务</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Document Selection */}
        <div className={`p-6 rounded-xl border-2 transition-all ${selectedDocId ? 'border-indigo-600 bg-indigo-50/50' : 'border-slate-200 bg-white hover:border-indigo-300'}`}>
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-100 rounded-lg text-indigo-700"><FileText className="w-6 h-6" /></div>
            <h3 className="font-semibold text-lg text-slate-800">1. 选择待审文档</h3>
          </div>
          <select
            className="w-full p-3 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
          >
            <option value="">-- 选择文档 --</option>
            {docs.filter(d => d.status === 'INDEXED').map(doc => (
              <option key={doc.id} value={doc.id}>{doc.filename} ({new Date(doc.upload_time).toLocaleDateString()})</option>
            ))}
          </select>
          {docs.length > 0 && docs.filter(d => d.status === 'INDEXED').length === 0 && (
            <p className="text-xs text-amber-600 mt-2 flex items-center"><AlertCircle className="w-3 h-3 mr-1" /> 暂无已索引的文档，请先上传文档并等待处理完成</p>
          )}
        </div>

        {/* Rule Group Selection */}
        <div className={`p-6 rounded-xl border-2 transition-all ${selectedGroupIds.length > 0 ? 'border-indigo-600 bg-indigo-50/50' : 'border-slate-200 bg-white hover:border-indigo-300'}`}>
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-100 rounded-lg text-indigo-700"><Shield className="w-6 h-6" /></div>
            <h3 className="font-semibold text-lg text-slate-800">2. 选择规则组</h3>
          </div>

          <div className="border border-slate-300 rounded-lg bg-white overflow-hidden">
            <div className="max-h-60 overflow-y-auto p-2 space-y-1">
              {flatGroups.map(g => (
                <div
                  key={g.id}
                  className={`flex items-center p-2 rounded cursor-pointer hover:bg-slate-50 ${selectedGroupIds.includes(g.id) ? 'bg-indigo-50' : ''}`}
                  style={{ paddingLeft: `${g.depth * 20 + 8}px` }}
                  onClick={() => toggleGroupSelection(g.id)}
                >
                  <div className={`mr-2 ${selectedGroupIds.includes(g.id) ? 'text-indigo-600' : 'text-slate-400'}`}>
                    {selectedGroupIds.includes(g.id) ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                  </div>
                  <span className={`text-sm ${selectedGroupIds.includes(g.id) ? 'text-indigo-700 font-medium' : 'text-slate-600'}`}>
                    {g.name}
                  </span>
                </div>
              ))}
              {groups.length === 0 && (
                <div className="p-4 text-center text-xs text-amber-600 flex items-center justify-center">
                  <AlertCircle className="w-3 h-3 mr-1" /> 暂无规则组
                </div>
              )}
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 ml-1">
            已选择 {selectedGroupIds.length} 个规则组
          </p>
        </div>
      </div>

      <div className="flex justify-center pt-6">
        <button
          onClick={startReview}
          disabled={!selectedDocId || selectedGroupIds.length === 0 || loading}
          className="flex items-center px-8 py-4 bg-indigo-600 text-white text-lg font-bold rounded-xl hover:bg-indigo-700 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 mr-3 animate-spin" />
              启动中...
            </>
          ) : (
            <>
              <Play className="w-5 h-5 mr-3 fill-current" />
              开始审查
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="text-center text-red-600 bg-red-50 p-3 rounded-lg mt-4">
          {error}
        </div>
      )}
    </div>
  );
};