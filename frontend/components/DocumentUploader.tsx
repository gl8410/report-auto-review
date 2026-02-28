import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Document, DocumentChunk } from '../types';
import { FileUp, FileText, CheckCircle2, Loader2, AlertCircle, Trash2, RefreshCw, Info, Eye, X, Download, RotateCcw } from 'lucide-react';
import { api } from '../services/api';

// Parse a datetime string from the backend as UTC (append Z if no tz info)
const parseUTC = (s: string) => new Date(/[Zz]|[+-]\d{2}:?\d{2}$/.test(s) ? s : s + 'Z');
const formatLocalTime = (s: string) => parseUTC(s).toLocaleString('zh-CN');

// Upload queue item type
interface UploadQueueItem {
  id: string;
  file: File;
  status: 'queued' | 'uploading' | 'completed' | 'failed';
  progress: number;
  error?: string;
}

export const DocumentUploader: React.FC = () => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [currentUpload, setCurrentUpload] = useState<UploadQueueItem | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  // Chunk Viewer State
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [showChunkModal, setShowChunkModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const docsRef = useRef<Document[]>([]);
  const uploadQueueRef = useRef<UploadQueueItem[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingQueueRef = useRef<boolean>(false);

  // Keep refs in sync with state
  useEffect(() => {
    docsRef.current = docs;
  }, [docs]);

  useEffect(() => {
    uploadQueueRef.current = uploadQueue;
  }, [uploadQueue]);

  const loadDocs = useCallback(async () => {
    try {
      const data = await api.getDocuments();
      setDocs(data);
      setError(null);
    } catch (e) {
      console.error(e);
      setError('Failed to load documents');
    }
  }, []);

  useEffect(() => {
    loadDocs();
    // Poll more frequently (every 5 seconds) when there are documents being processed
    const interval = setInterval(() => {
      const hasProcessing = docsRef.current.some(d =>
        d.status === 'UPLOADING' || d.status === 'PARSING' || d.status === 'EMBEDDING'
      );
      if (hasProcessing) {
        loadDocs();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [loadDocs]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadDocs();
    setIsRefreshing(false);
  };

  // Process upload queue
  const processUploadQueue = useCallback(async () => {
    if (isProcessingQueueRef.current) return;

    // Find next item to process from ref to avoid stale closures
    const queue = uploadQueueRef.current;
    const nextItem = queue.find(item => item.status === 'queued');
    
    if (!nextItem) {
      isProcessingQueueRef.current = false;
      return;
    }

    isProcessingQueueRef.current = true;
    setCurrentUpload(nextItem);

    // Update item status to uploading
    setUploadQueue(prevQueue => prevQueue.map(item =>
      item.id === nextItem.id ? { ...item, status: 'uploading' as const } : item
    ));

    // Start the upload
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // Upload the document with progress tracking
      const newDoc = await api.uploadDocument(
        nextItem.file,
        abortController.signal,
        (progress) => {
          setUploadQueue(q => q.map(item =>
            item.id === nextItem.id ? { ...item, progress } : item
          ));
        }
      );

      // Add the new document to the list (guard against polling race: loadDocs may have already added it)
      setDocs(prevDocs =>
        prevDocs.some(d => d.id === newDoc.id) ? prevDocs : [newDoc, ...prevDocs]
      );

      // Mark as completed
      setUploadQueue(q => q.map(item =>
        item.id === nextItem.id ? { ...item, status: 'completed' as const, progress: 100 } : item
      ));

      // Start polling for this document
      const pollInterval = setInterval(async () => {
        // Check if component is still mounted
        if (!docsRef.current) {
          clearInterval(pollInterval);
          return;
        }

        try {
          const updatedDoc = await api.getDocument(newDoc.id);
          setDocs(prevDocs => {
            // Only update if status changed to avoid unnecessary re-renders
            const currentDoc = prevDocs.find(d => d.id === newDoc.id);
            if (currentDoc && currentDoc.status === updatedDoc.status) {
              return prevDocs;
            }
            return prevDocs.map(d => d.id === newDoc.id ? updatedDoc : d);
          });

          if (updatedDoc.status === 'DONE' || updatedDoc.status === 'FAILED') {
            clearInterval(pollInterval);
          }
        } catch (e) {
          // Don't log 404s or network errors during polling to avoid console spam
          // Just stop polling if it seems permanent
          clearInterval(pollInterval);
        }
      }, 2000); // Poll every 2 seconds

      setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);

      // Remove from queue after 2 seconds
      setTimeout(() => {
        setUploadQueue(q => q.filter(item => item.id !== nextItem.id));
      }, 2000);

    } catch (e: any) {
      if (e.name === 'AbortError') {
        // Remove cancelled item from queue
        setUploadQueue(q => q.filter(item => item.id !== nextItem.id));
      } else {
        // Mark as failed
        setUploadQueue(q => q.map(item =>
          item.id === nextItem.id
            ? { ...item, status: 'failed' as const, error: e.message || 'Upload failed' }
            : item
        ));

        // Remove failed item after 5 seconds
        setTimeout(() => {
          setUploadQueue(q => q.filter(item => item.id !== nextItem.id));
        }, 5000);
      }
    } finally {
      abortControllerRef.current = null;
      setCurrentUpload(null);
      isProcessingQueueRef.current = false;

      // Process next item in queue
      setTimeout(() => processUploadQueue(), 500);
    }
  }, []);

  // Auto-process queue when new items are added
  useEffect(() => {
    if (uploadQueue.length > 0 && !isProcessingQueueRef.current) {
      processUploadQueue();
    }
  }, [uploadQueue.length, processUploadQueue]);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Check file size (200MB limit)
    const maxSize = 200 * 1024 * 1024; // 200MB in bytes
    if (file.size > maxSize) {
      setError(`文件大小超过限制（最大 200MB）。当前文件大小：${(file.size / 1024 / 1024).toFixed(2)}MB`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    // Add to upload queue
    const queueItem: UploadQueueItem = {
      id: `upload-${Date.now()}-${Math.random()}`,
      file,
      status: 'queued',
      progress: 0
    };

    setUploadQueue(prev => [...prev, queueItem]);
    setError(null);

    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleCancelUpload = async (doc: Document) => {
    // If currently uploading, abort the request
    if (abortControllerRef.current && currentUpload && doc.status === 'UPLOADING') {
      abortControllerRef.current.abort();
    }

    // Delete the document from backend
    setCancellingId(doc.id);
    try {
      await api.deleteDocument(doc.id);
      setDocs(prevDocs => prevDocs.filter(d => d.id !== doc.id));
    } catch (e: any) {
      setError(e.message || "Failed to cancel upload");
    } finally {
      setCancellingId(null);
    }
  };

  const handleCancelQueueItem = (queueItemId: string) => {
    setUploadQueue(q => q.filter(item => item.id !== queueItemId));
  };

  const handleDelete = async (doc: Document) => {
    if (!confirm(`确定要删除文档 "${doc.filename}" 吗？此操作不可恢复。`)) return;

    setDeletingId(doc.id);
    try {
      await api.deleteDocument(doc.id);
      await loadDocs();
    } catch (e: any) {
      setError(e.message || "Failed to delete document");
    } finally {
      setDeletingId(null);
    }
  };

  const handleRetry = async (doc: Document) => {
    setRetryingId(doc.id);
    setError(null);
    try {
      await api.retryDocument(doc.id);
      await loadDocs();
    } catch (e: any) {
      setError(e.message || "Failed to retry document");
    } finally {
      setRetryingId(null);
    }
  };

  const handleDownloadMarkdown = async (doc: Document) => {
    try {
      await api.downloadDocumentMarkdown(doc.id, doc.filename);
    } catch (e: any) {
      setError(e.message || "Failed to download markdown");
    }
  };

  const handleDownloadOriginal = async (doc: Document) => {
    try {
      await api.downloadDocumentOriginal(doc.id, doc.filename);
    } catch (e: any) {
      setError(e.message || "Failed to download original file");
    }
  };

  const handleViewChunks = async (doc: Document) => {
    setSelectedDoc(doc);
    setShowChunkModal(true);
    setIsLoadingChunks(true);
    setChunks([]);
    try {
      const data = await api.getDocumentChunks(doc.id);
      setChunks(data);
    } catch (e: any) {
      console.error(e);
      setError("Failed to load chunks");
    } finally {
      setIsLoadingChunks(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DONE':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-100">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> 已完成
          </span>
        );
      case 'UPLOADING':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100">
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 上传中...
          </span>
        );
      case 'PARSING':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-100">
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 解析中...
          </span>
        );
      case 'EMBEDDING':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-purple-700 bg-purple-50 px-2.5 py-1 rounded-full border border-purple-100">
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 向量化中...
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-red-700 bg-red-50 px-2.5 py-1 rounded-full border border-red-100">
            <AlertCircle className="w-3.5 h-3.5 mr-1.5" /> 处理失败
          </span>
        );
      default:
        return <span className="text-xs text-slate-500">{status}</span>;
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-end border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">文档仓库</h2>
          <p className="text-slate-500 mt-1">上传待审查的工程报告文档，支持 PDF、DOCX、PPT 格式（最大200MB）。文档需完成处理后才能用于审查。</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center px-3 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 disabled:opacity-50"
            title="刷新列表"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,.docx,.doc,.ppt,.pptx"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm transition-colors font-medium relative"
          >
            {currentUpload ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileUp className="w-4 h-4 mr-2" />}
            上传文档
            {uploadQueue.length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {uploadQueue.filter(i => i.status !== 'completed').length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Upload Queue */}
      {uploadQueue.length > 0 && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
            <h3 className="text-sm font-semibold text-blue-900">
              上传队列 ({uploadQueue.filter(i => i.status !== 'completed').length} 个文件)
            </h3>
          </div>
          <div className="space-y-2">
            {uploadQueue.map((item) => (
              <div
                key={item.id}
                className={`bg-white rounded-lg p-3 border ${
                  item.status === 'uploading' ? 'border-blue-300 shadow-sm' :
                  item.status === 'completed' ? 'border-green-300' :
                  item.status === 'failed' ? 'border-red-300' :
                  'border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <FileText className={`w-4 h-4 flex-shrink-0 ${
                      item.status === 'uploading' ? 'text-blue-600' :
                      item.status === 'completed' ? 'text-green-600' :
                      item.status === 'failed' ? 'text-red-600' :
                      'text-gray-400'
                    }`} />
                    <span className="text-sm font-medium text-gray-900 truncate">
                      {item.file.name}
                    </span>
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      ({(item.file.size / 1024 / 1024).toFixed(2)} MB)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.status === 'queued' && (
                      <>
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">等待中</span>
                        <button
                          onClick={() => handleCancelQueueItem(item.id)}
                          className="text-gray-400 hover:text-red-600 transition-colors"
                          title="取消"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {item.status === 'uploading' && (
                      <span className="text-xs text-blue-600 font-medium">{item.progress}%</span>
                    )}
                    {item.status === 'completed' && (
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    )}
                    {item.status === 'failed' && (
                      <AlertCircle className="w-4 h-4 text-red-600" />
                    )}
                  </div>
                </div>
                {item.status === 'uploading' && (
                  <div className="w-full bg-blue-100 rounded-full h-1.5">
                    <div
                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                )}
                {item.status === 'failed' && item.error && (
                  <p className="text-xs text-red-600 mt-1">{item.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-red-800 font-medium">操作失败</p>
            <p className="text-red-600 text-sm mt-1">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
        <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-medium">文档处理流程</p>
          <ol className="mt-1 list-decimal list-inside text-blue-700">
            <li>上传文档 (PDF/DOCX/PPT，最大200MB)</li>
            <li>使用 MinerU API 提取文本和图片内容为 Markdown</li>
            <li>文本分块并向量化存储到 ChromaDB</li>
            <li>状态变为"已完成"后可用于审查</li>
            <li>可下载原始文件和提取的 Markdown 文件</li>
          </ol>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-4 font-semibold text-slate-700">文件名</th>
              <th className="px-6 py-4 font-semibold text-slate-700">处理状态</th>
              <th className="px-6 py-4 font-semibold text-slate-700">上传时间</th>
              <th className="px-6 py-4 font-semibold text-slate-700 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {docs.map(doc => (
              <tr
                key={doc.id}
                className="hover:bg-slate-50 transition-colors"
              >
                <td className="px-6 py-4 font-medium text-slate-900">
                  <div className="flex items-center">
                    <div className="p-2 bg-slate-100 rounded-lg mr-3">
                      <FileText className="w-5 h-5 text-indigo-600" />
                    </div>
                    <span className="truncate max-w-xs" title={doc.filename}>{doc.filename}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  {getStatusBadge(doc.status)}
                </td>
                <td className="px-6 py-4 text-slate-500 text-xs font-mono">
                  {formatLocalTime(doc.upload_time)}
                </td>
                <td className="px-6 py-4 text-center">
                  <div className="flex items-center justify-center gap-2">
                    {/* Cancel Button (only for uploading/parsing/embedding documents) */}
                    {(doc.status === 'UPLOADING' || doc.status === 'PARSING' || doc.status === 'EMBEDDING') && (
                      <button
                        onClick={() => handleCancelUpload(doc)}
                        disabled={cancellingId === doc.id}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50 transition-colors"
                        title="取消处理"
                      >
                        {cancellingId === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <X className="w-4 h-4" />
                        )}
                      </button>
                    )}

                    {/* Download Original File */}
                    <button
                      onClick={() => handleDownloadOriginal(doc)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title="下载原始文件"
                      disabled={doc.status === 'UPLOADING'}
                    >
                      <Download className="w-4 h-4" />
                    </button>

                    {/* Download Markdown File */}
                    <button
                      onClick={() => handleDownloadMarkdown(doc)}
                      className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title="下载 Markdown 文件"
                      disabled={doc.status !== 'DONE'}
                    >
                      <FileText className="w-4 h-4" />
                    </button>

                    {/* View Chunks */}
                    <button
                      onClick={() => handleViewChunks(doc)}
                      className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title="查看分块详情"
                      disabled={doc.status !== 'DONE'}
                    >
                      <Eye className="w-4 h-4" />
                    </button>

                    {/* Retry Button (only for failed documents) */}
                    {doc.status === 'FAILED' && (
                      <button
                        onClick={() => handleRetry(doc)}
                        disabled={retryingId === doc.id}
                        className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg disabled:opacity-50 transition-colors"
                        title="重试处理"
                      >
                        {retryingId === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <RotateCcw className="w-4 h-4" />
                        )}
                      </button>
                    )}

                    {/* Delete Button (only show for DONE or FAILED status) */}
                    {(doc.status === 'DONE' || doc.status === 'FAILED') && (
                      <button
                        onClick={() => handleDelete(doc)}
                        disabled={deletingId === doc.id}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50 transition-colors"
                        title="删除文档"
                      >
                        {deletingId === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                  {/* Show error message if failed */}
                  {doc.status === 'FAILED' && doc.error_message && (
                    <div className="text-xs text-red-600 mt-1 max-w-xs mx-auto truncate" title={doc.error_message}>
                      {doc.error_message}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {docs.length === 0 && (
              <tr>
                <td colSpan={4} className="px-6 py-16 text-center text-slate-400">
                  <FileUp className="w-12 h-12 mx-auto mb-3 text-slate-200" />
                  <p>暂无上传的文档</p>
                  <p className="text-sm mt-1">点击上方按钮上传 PDF 或 DOCX 文件</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Chunk Viewer Modal */}
      {showChunkModal && selectedDoc && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl h-[80vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">文档分块详情</h3>
                <p className="text-sm text-slate-500">{selectedDoc.filename}</p>
              </div>
              <button
                onClick={() => setShowChunkModal(false)}
                className="p-2 hover:bg-slate-100 rounded-full text-slate-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-auto p-4 bg-slate-50">
              {isLoadingChunks ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500">
                  <Loader2 className="w-8 h-8 animate-spin mb-2" />
                  <p>正在加载分块数据...</p>
                </div>
              ) : chunks.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400">
                  <AlertCircle className="w-12 h-12 mb-2 opacity-20" />
                  <p>未找到分块数据</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                      <div className="text-sm text-slate-500">总分块数</div>
                      <div className="text-2xl font-bold text-indigo-600">{chunks.length}</div>
                    </div>
                    <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                      <div className="text-sm text-slate-500">平均字数/块</div>
                      <div className="text-2xl font-bold text-emerald-600">
                        {Math.round(chunks.reduce((acc, c) => acc + c.word_count, 0) / chunks.length)}
                      </div>
                    </div>
                    <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
                      <div className="text-sm text-slate-500">平均句子/块</div>
                      <div className="text-2xl font-bold text-amber-600">
                        {Math.round(chunks.reduce((acc, c) => acc + c.sentence_count, 0) / chunks.length)}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {chunks.map((chunk) => (
                      <div key={chunk.id} className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
                        <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex justify-between items-center">
                          <span className="font-mono text-xs font-semibold text-slate-500">
                            Chunk #{chunk.chunk_index}
                          </span>
                          <div className="flex gap-3 text-xs text-slate-400">
                            <span>{chunk.word_count} 字</span>
                            <span>{chunk.sentence_count} 句</span>
                          </div>
                        </div>
                        <div className="p-4 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap font-sans">
                          {chunk.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};