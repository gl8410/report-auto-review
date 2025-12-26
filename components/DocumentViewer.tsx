import React, { useState, useEffect, useRef } from 'react';
import { FileLocation } from '../types';
import { api } from '../services/api';
import { Loader2, AlertCircle, Search, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface DocumentViewerProps {
    taskId: string;
    fileType: 'draft' | 'approved';
    fileIndex: number;
    filename?: string;
    location?: FileLocation | null;
    title: string;
    highlightText?: string;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
    taskId,
    fileType,
    fileIndex,
    filename,
    location,
    title,
    highlightText
}) => {
    const [fileUrl, setFileUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [numPages, setNumPages] = useState<number | null>(null);
    const [pageNumber, setPageNumber] = useState<number>(1);
    const [scale, setScale] = useState(1.0);
    const [pdfDocument, setPdfDocument] = useState<any>(null);
    const [searchStatus, setSearchStatus] = useState<'idle' | 'searching' | 'found' | 'not-found'>('idle');

    // Fetch file URL
    useEffect(() => {
        let active = true;
        const fetchFile = async () => {
            setLoading(true);
            setError(null);
            try {
                const url = await api.getAnalysisFile(taskId, fileType, fileIndex);
                if (active) {
                    setFileUrl(url);
                }
            } catch (e: any) {
                if (active) {
                    setError(e.message || "加载文件失败");
                }
            } finally {
                if (active) {
                    setLoading(false);
                }
            }
        };

        fetchFile();
        return () => { active = false; };
    }, [taskId, fileType, fileIndex]);

    // Handle location update
    useEffect(() => {
        if (location?.page) {
            setPageNumber(location.page);
            setSearchStatus('found');
        } else {
            setSearchStatus('idle');
        }
    }, [location]);

    // Handle highlight text search
    useEffect(() => {
        if (!pdfDocument || !highlightText || location?.page) return;

        const searchInPdf = async () => {
            setSearchStatus('searching');
            try {
                // Search all pages
                const maxPagesToCheck = pdfDocument.numPages;
                let foundPage = -1;
                
                // Prepare search chunks (robustness against OCR errors)
                const cleanSearchText = highlightText.replace(/\s+/g, '');
                const chunks = [
                    cleanSearchText.substring(0, 20),
                    cleanSearchText.substring(20, 40),
                    cleanSearchText.substring(40, 60)
                ].filter(c => c.length > 10);

                if (chunks.length === 0 && cleanSearchText.length > 0) {
                    chunks.push(cleanSearchText);
                }

                for (let i = 1; i <= maxPagesToCheck; i++) {
                    const page = await pdfDocument.getPage(i);
                    const textContent = await page.getTextContent();
                    const text = textContent.items.map((item: any) => item.str).join('');
                    
                    // Remove whitespace for fuzzy matching
                    const cleanPageText = text.replace(/\s+/g, '');
                    
                    // Check if any chunk matches
                    if (chunks.some(chunk => cleanPageText.includes(chunk))) {
                        foundPage = i;
                        break;
                    }
                }

                if (foundPage !== -1) {
                    setPageNumber(foundPage);
                    setSearchStatus('found');
                } else {
                    setSearchStatus('not-found');
                }
            } catch (e) {
                console.error("Search failed", e);
                setSearchStatus('not-found');
            }
        };

        searchInPdf();
    }, [pdfDocument, highlightText, location]);

    const onDocumentLoadSuccess = (pdf: any) => {
        setNumPages(pdf.numPages);
        setPdfDocument(pdf);
    };

    const isPdf = filename?.toLowerCase().endsWith('.pdf');

    return (
        <div className="h-full flex flex-col bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 p-2 flex justify-between items-center shadow-sm z-10">
                <div className="flex items-center gap-2 overflow-hidden">
                    <h4 className="font-semibold text-slate-800 text-sm truncate max-w-[200px]" title={title}>{title}</h4>
                    {filename && <span className="text-xs text-slate-500 truncate max-w-[150px]" title={filename}>({filename})</span>}
                </div>
                
                <div className="flex items-center gap-1">
                    <button onClick={() => setScale(s => Math.max(0.5, s - 0.1))} className="p-1 hover:bg-slate-100 rounded" title="缩小">
                        <ZoomOut className="w-4 h-4 text-slate-600" />
                    </button>
                    <span className="text-xs text-slate-500 w-8 text-center">{Math.round(scale * 100)}%</span>
                    <button onClick={() => setScale(s => Math.min(2.0, s + 0.1))} className="p-1 hover:bg-slate-100 rounded" title="放大">
                        <ZoomIn className="w-4 h-4 text-slate-600" />
                    </button>
                    <div className="h-4 w-px bg-slate-300 mx-1" />
                    <button 
                        onClick={() => setPageNumber(p => Math.max(1, p - 1))} 
                        disabled={pageNumber <= 1}
                        className="p-1 hover:bg-slate-100 rounded disabled:opacity-30"
                    >
                        <ChevronLeft className="w-4 h-4 text-slate-600" />
                    </button>
                    <span className="text-xs text-slate-500">
                        {pageNumber} / {numPages || '-'}
                    </span>
                    <button 
                        onClick={() => setPageNumber(p => Math.min(numPages || 1, p + 1))} 
                        disabled={pageNumber >= (numPages || 1)}
                        className="p-1 hover:bg-slate-100 rounded disabled:opacity-30"
                    >
                        <ChevronRight className="w-4 h-4 text-slate-600" />
                    </button>
                </div>
            </div>

            {/* Content Wrapper */}
            <div className="flex-1 relative overflow-hidden bg-slate-100">
                {/* Scrollable Area */}
                <div className="absolute inset-0 overflow-auto p-4">
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-20">
                            <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
                        </div>
                    )}

                    {error && (
                        <div className="flex flex-col items-center justify-center text-red-500 p-8">
                            <AlertCircle className="w-8 h-8 mb-2" />
                            <p className="text-sm">{error}</p>
                        </div>
                    )}

                    {!loading && !error && fileUrl && (
                        isPdf ? (
                            <div className="inline-block min-w-full text-center">
                                <Document
                                    file={fileUrl}
                                    onLoadSuccess={onDocumentLoadSuccess}
                                    loading={<div className="flex items-center gap-2 text-slate-500"><Loader2 className="w-4 h-4 animate-spin" /> 加载文档...</div>}
                                    error={<div className="text-red-500 text-sm">无法加载PDF文档</div>}
                                    className="shadow-lg inline-block"
                                >
                                    <Page
                                        pageNumber={pageNumber}
                                        scale={scale}
                                        renderTextLayer={true}
                                        renderAnnotationLayer={true}
                                        className="bg-white"
                                        customTextRenderer={({ str, itemIndex }) => {
                                            // Simple highlighting logic
                                            if (highlightText && str.includes(highlightText.substring(0, 10))) {
                                                return `<span class="bg-yellow-200">${str}</span>`;
                                            }
                                            return str;
                                        }}
                                    />
                                </Document>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center text-slate-500 mt-10">
                                <div className="w-16 h-16 bg-slate-200 rounded-full flex items-center justify-center mb-4">
                                    <AlertCircle className="w-8 h-8 text-slate-400" />
                                </div>
                                <p className="font-medium">不支持预览该文件格式</p>
                                <p className="text-sm mt-1 text-slate-400">仅支持 PDF 文件预览</p>
                                <a
                                    href={fileUrl}
                                    download={filename}
                                    className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700 transition-colors"
                                >
                                    下载文件查看
                                </a>
                            </div>
                        )
                    )}
                </div>

                {/* Floating Indicators (Fixed relative to viewer) */}
                {searchStatus === 'searching' && (
                    <div className="absolute bottom-4 right-4 bg-black/70 text-white px-3 py-1 rounded-full text-xs flex items-center z-30 pointer-events-none">
                        <Search className="w-3 h-3 mr-1 animate-pulse" /> 正在定位内容...
                    </div>
                )}
                
                {searchStatus === 'not-found' && (
                    <div className="absolute bottom-4 right-4 bg-red-600/80 text-white px-3 py-1 rounded-full text-xs flex items-center z-30 pointer-events-none">
                        <AlertCircle className="w-3 h-3 mr-1" /> 无定位信息
                    </div>
                )}
            </div>
        </div>
    );
};
