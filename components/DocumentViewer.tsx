import React from 'react';
import { FileLocation } from '../types';

interface DocumentViewerProps {
    taskId: string;
    fileType: 'draft' | 'approved';
    fileIndex: number;
    location?: FileLocation | null;
    title: string;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
    taskId,
    fileType,
    fileIndex,
    title
}) => {
    return (
        <div className="h-full flex flex-col bg-slate-50">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 p-3 flex justify-between items-center">
                <h4 className="font-semibold text-slate-800">{title}</h4>
            </div>

            {/* Content - Temporary placeholder */}
            <div className="flex-1 overflow-auto p-4">
                <div className="bg-white p-6 rounded-lg shadow-sm">
                    <div className="text-center text-slate-600 mb-4">
                        <p className="text-sm">📄 文档查看器开发中...</p>
                        <p className="text-xs text-slate-400 mt-2">Document viewer feature is under development</p>
                    </div>
                    <div className="mt-4 p-4 bg-slate-50 rounded border border-slate-200">
                        <p className="text-xs text-slate-500 mb-2">文件信息 / File Info:</p>
                        <p className="text-sm">Task ID: {taskId}</p>
                        <p className="text-sm">Type: {fileType}</p>
                        <p className="text-sm">Index: {fileIndex}</p>
                    </div>
                </div>
            </div>
        </div>
    );
};
