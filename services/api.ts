import { RuleGroup, Rule, Document, DocumentChunk, ReviewTask, ReviewResult, ComparisonDocument, ComparisonResult } from '../types';
import { supabase } from './supabase';

const API_BASE = 'http://localhost:8000/api/v1';
// const API_BASE = 'http://10.254.68.193:8000/api/v1';

const getHeaders = async (contentType = 'application/json') => {
  const { data: { session } } = await supabase.auth.getSession();
  const headers: HeadersInit = { 'Content-Type': contentType };
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  return headers;
};

// Helper for requests without body (GET, DELETE) or with FormData
const getAuthHeaders = async () => {
  const { data: { session } } = await supabase.auth.getSession();
  const headers: HeadersInit = {};
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  return headers;
};

export const api = {
  // ============== Rule Groups ==============
  getRuleGroups: async (): Promise<RuleGroup[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rule-groups`, { headers });
    if (!res.ok) throw new Error('Failed to fetch rule groups');
    return res.json();
  },

  createRuleGroup: async (name: string, description: string, parentId?: string): Promise<RuleGroup> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/rule-groups`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name, description, parent_id: parentId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create group');
    }
    return res.json();
  },

  updateRuleGroup: async (groupId: string, name: string, description?: string, parentId?: string): Promise<RuleGroup> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ name, description, parent_id: parentId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update group');
    }
    return res.json();
  },

  deleteRuleGroup: async (groupId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}`, { method: 'DELETE', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete group');
    }
  },

  // ============== Rules ==============
  getRules: async (groupId: string, recursive: boolean = false): Promise<Rule[]> => {
    const url = new URL(`${API_BASE}/rule-groups/${groupId}/rules`);
    if (recursive) url.searchParams.append('recursive', 'true');
    const headers = await getAuthHeaders();
    const res = await fetch(url.toString(), { headers });
    if (!res.ok) throw new Error('Failed to fetch rules');
    return res.json();
  },

  createRule: async (groupId: string, rule: Partial<Rule>): Promise<Rule> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/rules`, {
      method: 'POST',
      headers,
      body: JSON.stringify(rule)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create rule');
    }
    return res.json();
  },

  updateRule: async (ruleId: string, rule: Partial<Rule>): Promise<Rule> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/rules/${ruleId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(rule)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update rule');
    }
    return res.json();
  },

  deleteRule: async (ruleId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rules/${ruleId}`, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed to delete rule');
  },

  // ============== File Upload ==============
  uploadRules: async (groupId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/upload`, {
      method: 'POST',
      headers,
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to upload rules');
    }
    return res.json();
  },

  // ============== CSV Import/Export ==============
  exportRulesCsv: async (groupId: string, groupName: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/export-csv`, { headers });
    if (!res.ok) throw new Error('Failed to export rules');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${groupName}_rules.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  importRulesCsv: async (groupId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/import-csv`, {
      method: 'POST',
      headers,
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to import CSV');
    }
    return res.json();
  },

  // ============== Documents ==============
  getDocuments: async (): Promise<Document[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents`, { headers });
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  getDocument: async (docId: string): Promise<Document> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch document');
    return res.json();
  },

  uploadDocument: async (
    file: File,
    signal?: AbortSignal,
    onProgress?: (progress: number) => void
  ): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const session = await supabase.auth.getSession();
    const token = session.data.session?.access_token;

    // Use XMLHttpRequest for progress tracking
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Handle abort signal
      if (signal) {
        signal.addEventListener('abort', () => {
          xhr.abort();
          reject(new DOMException('Upload aborted', 'AbortError'));
        });
      }

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            onProgress(progress);
          }
        });
      }

      // Handle completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (e) {
            reject(new Error('Failed to parse response'));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || 'Upload failed'));
          } catch (e) {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      // Handle errors
      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new DOMException('Upload aborted', 'AbortError'));
      });

      // Send request
      xhr.open('POST', `${API_BASE}/documents`);
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      xhr.send(formData);
    });
  },

  deleteDocument: async (docId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete document');
    }
  },

  retryDocument: async (docId: string): Promise<Document> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}/retry`, { method: 'POST', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retry document');
    }
    return res.json();
  },

  downloadDocumentMarkdown: async (docId: string, filename: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}/download-markdown`, { headers });
    if (!res.ok) throw new Error('Failed to download markdown');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename.replace(/\.[^/.]+$/, '')}.md`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  downloadDocumentOriginal: async (docId: string, filename: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}/download-original`, { headers });
    if (!res.ok) throw new Error('Failed to download original file');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  getDocumentChunks: async (docId: string): Promise<DocumentChunk[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/documents/${docId}/chunks`, { headers });
    if (!res.ok) throw new Error('Failed to fetch document chunks');
    return res.json();
  },

  // ============== Reviews ==============
  startReview: async (documentId: string, ruleGroupIds: string[], comparisonDocIds?: string[]): Promise<any> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/reviews/start`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        document_id: documentId,
        rule_group_ids: ruleGroupIds,
        comparison_document_ids: comparisonDocIds
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start review');
    }
    return res.json();
  },

  getReviewTask: async (taskId: string): Promise<any> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch task status');
    return res.json();
  },

  getReviewResults: async (taskId: string): Promise<any[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}/results`, { headers });
    if (!res.ok) throw new Error('Failed to fetch results');
    return res.json();
  },

  getReviewTasks: async (): Promise<any[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews`, { headers });
    if (!res.ok) throw new Error('Failed to fetch review tasks');
    return res.json();
  },

  deleteReviewTask: async (taskId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}`, { method: 'DELETE', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete review task');
    }
  },

  cancelReviewTask: async (taskId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}/cancel`, { method: 'POST', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to cancel review task');
    }
  },

  // ============== Review Result Items ==============
  getResult: async (resultId: string): Promise<ReviewResult> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/results/${resultId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch result');
    return res.json();
  },

  updateResult: async (resultId: string, data: {
    result_code?: string;
    reasoning?: string;
    evidence?: string;
    suggestion?: string;
  }): Promise<ReviewResult> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/results/${resultId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update result');
    }
    return res.json();
  },

  deleteResult: async (resultId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/results/${resultId}`, { method: 'DELETE', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete result');
    }
  },

  // ============== Summary PDF Report ==============
  downloadSummaryPdf: async (taskId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}/summary-pdf`, { headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate PDF');
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `review_summary_${taskId.substring(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  // Legacy aliases for backward compatibility
  getTaskStatus: async (taskId: string): Promise<ReviewTask> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch task status');
    return res.json();
  },
  getResults: async (taskId: string): Promise<ReviewResult[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}/results`, { headers });
    if (!res.ok) throw new Error('Failed to fetch results');
    return res.json();
  },

  // ============== History Analysis ==============
  startHistoryAnalysis: async (draftFiles: File[], approvedFiles: File[]): Promise<any> => {
    const formData = new FormData();
    draftFiles.forEach(f => formData.append('draft_files', f));
    approvedFiles.forEach(f => formData.append('approved_files', f));
    const headers = await getAuthHeaders();

    const res = await fetch(`${API_BASE}/history-analysis`, {
      method: 'POST',
      headers,
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start history analysis');
    }
    return res.json();
  },

  getHistoryAnalysis: async (taskId: string): Promise<any> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/history-analysis/${taskId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch history analysis');
    return res.json();
  },

  updateOpinion: async (opinionId: string, data: { opinion?: string, risk_level?: string, review_type?: string }): Promise<any> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/history-analysis/opinions/${opinionId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to update opinion');
    return res.json();
  },

  deleteOpinion: async (opinionId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/history-analysis/opinions/${opinionId}`, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed to delete opinion');
  },

  getAnalysisFile: async (taskId: string, fileType: 'draft' | 'approved', fileIndex: number): Promise<string> => {
    // Handling auth for blob fetch might be tricky if backend requires it.
    // For now assuming getAuthHeaders works or we add token to URL?
    // Headers is better.
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/history-analysis/files/${taskId}/${fileType}/${fileIndex}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch analysis file');
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },

  convertOpinionToRule: async (opinionId: string, ruleGroupIds: string[]): Promise<any> => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/history-analysis/opinions/${opinionId}/convert`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ rule_group_ids: ruleGroupIds })
    });
    if (!res.ok) throw new Error('Failed to convert opinion to rule');
    return res.json();
  },

  // ============== Comparison Documents (Module 6) ==============
  getComparisonDocuments: async (): Promise<ComparisonDocument[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents`, { headers });
    if (!res.ok) throw new Error('Failed to fetch comparison documents');
    return res.json();
  },

  getComparisonDocument: async (docId: string): Promise<ComparisonDocument> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents/${docId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch comparison document');
    return res.json();
  },

  uploadComparisonDocument: async (
    file: File,
    signal?: AbortSignal,
    onProgress?: (progress: number) => void
  ): Promise<ComparisonDocument> => {
    const formData = new FormData();
    formData.append('file', file);
    const session = await supabase.auth.getSession();
    const token = session.data.session?.access_token;

    // Use XMLHttpRequest for progress tracking
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Handle abort signal
      if (signal) {
        signal.addEventListener('abort', () => {
          xhr.abort();
          reject(new DOMException('Upload aborted', 'AbortError'));
        });
      }

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            onProgress(progress);
          }
        });
      }

      // Handle completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (e) {
            reject(new Error('Failed to parse response'));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || 'Upload failed'));
          } catch (e) {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      // Handle errors
      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new DOMException('Upload aborted', 'AbortError'));
      });

      // Send request
      xhr.open('POST', `${API_BASE}/comparison-documents`);
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      xhr.send(formData);
    });
  },

  deleteComparisonDocument: async (docId: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents/${docId}`, { method: 'DELETE', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete comparison document');
    }
  },

  retryComparisonDocument: async (docId: string): Promise<ComparisonDocument> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents/${docId}/retry`, { method: 'POST', headers });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retry comparison document');
    }
    return res.json();
  },

  downloadComparisonMarkdown: async (docId: string, filename: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents/${docId}/download-markdown`, { headers });
    if (!res.ok) throw new Error('Failed to download markdown');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename.replace(/\.[^/.]+$/, '')}.md`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  downloadComparisonOriginal: async (docId: string, filename: string): Promise<void> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/comparison-documents/${docId}/download-original`, { headers });
    if (!res.ok) throw new Error('Failed to download original file');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  getComparisonResults: async (taskId: string): Promise<ComparisonResult[]> => {
    const headers = await getAuthHeaders();
    const res = await fetch(`${API_BASE}/reviews/${taskId}/comparison-results`, { headers });
    if (!res.ok) throw new Error('Failed to fetch comparison results');
    return res.json();
  }
};