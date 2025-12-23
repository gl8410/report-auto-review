import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Document, DocumentChunk } from '../types';
import { FileUp, FileText, CheckCircle2, Loader2, AlertCircle, Trash2, RefreshCw, Info, Eye, X } from 'lucide-react';
import { api } from '../services/api';

export const DocumentUploader: React.FC = () => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Chunk Viewer State
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);
  const [showChunkModal, setShowChunkModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const docsRef = useRef<Document[]>([]);

  // Keep docsRef in sync with docs state
  useEffect(() => {
    docsRef.current = docs;
  }, [docs]);

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
    // Poll every 3 seconds when there are documents being processed
    const interval = setInterval(() => {
      const hasProcessing = docsRef.current.some(d => d.status === 'PARSING' || d.status === 'UPLOADED');
      if (hasProcessing) {
        loadDocs();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [loadDocs]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadDocs();
    setIsRefreshing(false);
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);
    try {
      await api.uploadDocument(file);
      await loadDocs();
    } catch (e: any) {
      setError(e.message || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
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
      case 'INDEXED':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-100">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> 已完成索引
          </span>
        );
      case 'PARSING':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-100">
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 解析中...
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-red-700 bg-red-50 px-2.5 py-1 rounded-full border border-red-100">
            <AlertCircle className="w-3.5 h-3.5 mr-1.5" /> 处理失败
          </span>
        );
      case 'UPLOADED':
        return (
          <span className="inline-flex items-center text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-100">
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> 等待处理...
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
          <p className="text-slate-500 mt-1">上传待审查的工程报告文档，支持 PDF、DOCX 格式。文档需完成索引后才能用于审查。</p>
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
            accept=".pdf,.docx,.doc"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-70 shadow-sm transition-colors font-medium"
          >
            {isUploading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileUp className="w-4 h-4 mr-2" />}
            上传文档
          </button>
        </div>
      </div>

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
            <li>上传文档 (PDF/DOCX)</li>
            <li>系统自动提取文本内容</li>
            <li>文本分块并向量化存储到 ChromaDB</li>
            <li>状态变为"已完成索引"后可用于审查</li>
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
                  {new Date(doc.upload_time).toLocaleString('zh-CN')}
                </td>
                <td className="px-6 py-4 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <button
                      onClick={() => handleViewChunks(doc)}
                      className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                      title="查看分块详情"
                      disabled={doc.status !== 'INDEXED'}
                    >
                      <Eye className="w-4 h-4" />
                    </button>
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
                  </div>
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