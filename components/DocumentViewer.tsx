import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { api } from '../services/api';
import { Loader2, AlertCircle, Search, ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface FileLocation {
    page: number;
    filename?: string;
}

interface DocumentViewerProps {
    taskId: string;
    fileType: 'draft' | 'approved';
    fileIndex: number;
    filename?: string;
    locationJson?: string | null;
    title: string;
    highlightText?: string;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
    taskId,
    fileType,
    fileIndex,
    filename,
    locationJson,
    title,
    highlightText
}) => {
    // 1. File Loading State
    const [fileUrl, setFileUrl] = useState<string | null>(null);
    const [docLoading, setDocLoading] = useState(false);
    const [docError, setDocError] = useState<string | null>(null);

    // 2. Viewer State
    const [numPages, setNumPages] = useState<number | null>(null);
    const [pageNumber, setPageNumber] = useState<number>(1);
    const [scale, setScale] = useState(1.0);
    const [pdfDocument, setPdfDocument] = useState<any>(null);

    // 3. Search/Location State
    const [searchStatus, setSearchStatus] = useState<'idle' | 'searching' | 'found' | 'not-found'>('idle');

    // Parse location safely
    const targetLocation = useMemo(() => {
        if (!locationJson) return null;
        try {
            return JSON.parse(locationJson) as FileLocation;
        } catch (e) {
            console.error("Failed to parse location JSON", e);
            return null;
        }
    }, [locationJson]);

    // Fetch File URL
    useEffect(() => {
        let active = true;
        const fetchFile = async () => {
            setDocLoading(true);
            setDocError(null);
            try {
                const url = await api.getAnalysisFile(taskId, fileType, fileIndex);
                if (active) setFileUrl(url);
            } catch (e: any) {
                if (active) setDocError(e.message || "无法加载文件");
            } finally {
                if (active) setDocLoading(false);
            }
        };
        fetchFile();
        return () => { active = false; };
    }, [taskId, fileType, fileIndex]);

    // Handle Location Jump
    useEffect(() => {
        if (targetLocation?.page) {
            setPageNumber(targetLocation.page);
            setSearchStatus('found');
        } else {
            // Location cleared or invalid, reset search status but don't reset page necessarily
            setSearchStatus('idle');
        }
    }, [targetLocation]);

    // Handle Text Search (if no explicit page location)
    useEffect(() => {
        if (!pdfDocument || !highlightText || targetLocation?.page) return;

        let active = true;
        const performSearch = async () => {
            setSearchStatus('searching');
            try {
                const cleanQuery = highlightText.replace(/\s+/g, '');
                // Create search chunks for robustness
                const chunks = [
                    cleanQuery.substring(0, 20),
                    cleanQuery.substring(20, 40)
                ].filter(c => c.length > 10);
                if (chunks.length === 0 && cleanQuery.length > 0) chunks.push(cleanQuery);

                if (chunks.length === 0) {
                    if (active) setSearchStatus('idle');
                    return;
                }

                // Scan pages (limit to first 50 for performance if needed, or scan all)
                for (let i = 1; i <= pdfDocument.numPages; i++) {
                    if (!active) return;
                    try {
                        const page = await pdfDocument.getPage(i);
                        const textContent = await page.getTextContent();
                        const text = textContent.items.map((item: any) => item.str).join('').replace(/\s+/g, '');
                        
                        if (chunks.some(chunk => text.includes(chunk))) {
                            if (active) {
                                setPageNumber(i);
                                setSearchStatus('found');
                            }
                            return;
                        }
                    } catch (e) {
                        // ignore page read error
                    }
                }
                if (active) setSearchStatus('not-found');
            } catch (e) {
                if (active) setSearchStatus('not-found');
            }
        };

        const timer = setTimeout(performSearch, 500); // Debounce search
        return () => { 
            active = false; 
            clearTimeout(timer); 
        };
    }, [pdfDocument, highlightText, targetLocation]);

    // Text Renderer for Highlighting
    const customTextRenderer = useCallback(({ str }: { str: string }) => {
        if (highlightText && str && str.length > 3) {
            // Simple robust check: is a part of this string in the highlight text?
            const cleanStr = str.replace(/\s+/g, '');
            const cleanHighlight = highlightText.replace(/\s+/g, '');
            
            // Check if this text segment is likely part of the highlighted section
            if (cleanHighlight.includes(cleanStr) || cleanStr.includes(cleanHighlight.substring(0, 20))) {
                 return `<span style="background-color: rgba(255, 255, 0, 0.4);">${str}</span>`;
            }
        }
        return str;
    }, [highlightText]);

    const onDocumentLoadSuccess = (pdf: any) => {
        setNumPages(pdf.numPages);
        setPdfDocument(pdf);
    };

    const isPdf = filename?.toLowerCase().endsWith('.pdf');

    return (
        <div className="h-full flex flex-col bg-slate-50">
            {/* Toolbar */}
            <div className="bg-white border-b border-slate-200 p-2 flex justify-between items-center shadow-sm z-10 px-4">
                <div className="flex items-center gap-2 overflow-hidden">
                    <h4 className="font-semibold text-slate-800 text-sm truncate max-w-[200px]" title={title}>{title}</h4>
                    {filename && <span className="text-xs text-slate-500 truncate max-w-[150px]">({filename})</span>}
                </div>
                
                <div className="flex items-center gap-2">
                    {searchStatus === 'searching' && <span className="text-xs text-indigo-600 animate-pulse flex items-center"><Search className="w-3 h-3 mr-1"/>搜索中...</span>}
                    {searchStatus === 'not-found' && <span className="text-xs text-red-500 flex items-center"><AlertCircle className="w-3 h-3 mr-1"/>未找到</span>}

                    <div className="flex items-center bg-slate-100 rounded-lg p-1">
                        <button onClick={() => setScale(s => Math.max(0.5, s - 0.2))} className="p-1 hover:bg-white rounded shadow-sm transition-all" title="缩小">
                            <ZoomOut className="w-4 h-4 text-slate-600" />
                        </button>
                        <span className="text-xs text-slate-600 w-12 text-center font-medium">{Math.round(scale * 100)}%</span>
                        <button onClick={() => setScale(s => Math.min(2.5, s + 0.2))} className="p-1 hover:bg-white rounded shadow-sm transition-all" title="放大">
                            <ZoomIn className="w-4 h-4 text-slate-600" />
                        </button>
                    </div>

                    <div className="flex items-center bg-slate-100 rounded-lg p-1 space-x-1">
                        <button 
                            onClick={() => setPageNumber(p => Math.max(1, p - 1))} 
                            disabled={pageNumber <= 1}
                            className="p-1 hover:bg-white rounded shadow-sm disabled:opacity-30 transition-all"
                        >
                            <ChevronLeft className="w-4 h-4 text-slate-600" />
                        </button>
                        <span className="text-xs text-slate-600 w-16 text-center">
                            {pageNumber} / {numPages || '-'}
                        </span>
                        <button 
                            onClick={() => setPageNumber(p => Math.min(numPages || 1, p + 1))} 
                            disabled={pageNumber >= (numPages || 1)}
                            className="p-1 hover:bg-white rounded shadow-sm disabled:opacity-30 transition-all"
                        >
                            <ChevronRight className="w-4 h-4 text-slate-600" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Viewer Area */}
            <div className="flex-1 relative overflow-hidden bg-slate-200/50">
                <div className="absolute inset-0 overflow-auto flex justify-center p-6">
                    {docLoading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-20 backdrop-blur-sm">
                            <div className="flex flex-col items-center">
                                <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mb-2" />
                                <span className="text-sm text-slate-600">加载文档中...</span>
                            </div>
                        </div>
                    )}

                    {docError && (
                        <div className="flex flex-col items-center justify-center text-red-500 mt-20">
                            <AlertCircle className="w-10 h-10 mb-3" />
                            <p className="font-medium">{docError}</p>
                        </div>
                    )}

                    {!docLoading && !docError && fileUrl && isPdf && (
                        <Document
                            file={fileUrl}
                            onLoadSuccess={onDocumentLoadSuccess}
                            loading={null}
                            error={<div className="text-red-500 mt-10">PDF加载失败</div>}
                            className="shadow-2xl"
                        >
                            <div className="border border-slate-200 bg-white" key={`page_${pageNumber}_${scale}`}>
                                <Page
                                    pageNumber={pageNumber}
                                    scale={scale}
                                    renderTextLayer={true}
                                    renderAnnotationLayer={true}
                                    loading={<div className="h-[800px] w-[600px] bg-white flex items-center justify-center text-slate-400">加载页面...</div>}
                                    customTextRenderer={customTextRenderer}
                                    onRenderError={() => console.warn('Render error suppressed')}
                                    onGetTextError={() => console.warn('Text error suppressed')}
                                />
                            </div>
                        </Document>
                    )}

                    {!docLoading && !isPdf && fileUrl && (
                        <div className="flex flex-col items-center justify-center text-slate-500 mt-20">
                            <AlertCircle className="w-12 h-12 text-slate-300 mb-4" />
                            <p>仅支持PDF预览</p>
                            <a href={fileUrl} className="mt-4 text-indigo-600 hover:underline">下载文件</a>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
