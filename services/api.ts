import { RuleGroup, Rule, Document, ReviewTask, ReviewResult } from '../types';

const API_BASE = 'http://localhost:8000';

export const api = {
  // ============== Rule Groups ==============
  getRuleGroups: async (): Promise<RuleGroup[]> => {
    const res = await fetch(`${API_BASE}/rule-groups`);
    if (!res.ok) throw new Error('Failed to fetch rule groups');
    return res.json();
  },

  createRuleGroup: async (name: string, description: string): Promise<RuleGroup> => {
    const res = await fetch(`${API_BASE}/rule-groups`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create group');
    }
    return res.json();
  },

  updateRuleGroup: async (groupId: string, name: string, description?: string): Promise<RuleGroup> => {
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update group');
    }
    return res.json();
  },

  deleteRuleGroup: async (groupId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete group');
    }
  },

  // ============== Rules ==============
  getRules: async (groupId: string): Promise<Rule[]> => {
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/rules`);
    if (!res.ok) throw new Error('Failed to fetch rules');
    return res.json();
  },

  createRule: async (groupId: string, rule: Partial<Rule>): Promise<Rule> => {
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to create rule');
    }
    return res.json();
  },

  updateRule: async (ruleId: string, rule: Partial<Rule>): Promise<Rule> => {
    const res = await fetch(`${API_BASE}/rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update rule');
    }
    return res.json();
  },

  deleteRule: async (ruleId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/rules/${ruleId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete rule');
  },

  // ============== File Upload ==============
  uploadRules: async (groupId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/upload`, {
      method: 'POST',
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
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/export-csv`);
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
    const res = await fetch(`${API_BASE}/rule-groups/${groupId}/import-csv`, {
      method: 'POST',
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
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  getDocument: async (docId: string): Promise<Document> => {
    const res = await fetch(`${API_BASE}/documents/${docId}`);
    if (!res.ok) throw new Error('Failed to fetch document');
    return res.json();
  },

  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/documents`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to upload document');
    }
    return res.json();
  },

  deleteDocument: async (docId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete document');
    }
  },

  // ============== Reviews ==============
  startReview: async (docId: string, groupId: string): Promise<{ task_id: string, status: string, message: string, total_rules: number }> => {
    const res = await fetch(`${API_BASE}/reviews/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: docId, rule_group_id: groupId })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start review');
    }
    return res.json();
  },

  getReviewTask: async (taskId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}`);
    if (!res.ok) throw new Error('Failed to fetch task status');
    return res.json();
  },

  getReviewResults: async (taskId: string): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}/results`);
    if (!res.ok) throw new Error('Failed to fetch results');
    return res.json();
  },

  getReviewTasks: async (): Promise<any[]> => {
    const res = await fetch(`${API_BASE}/reviews`);
    if (!res.ok) throw new Error('Failed to fetch review tasks');
    return res.json();
  },

  deleteReviewTask: async (taskId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete review task');
    }
  },

  cancelReviewTask: async (taskId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}/cancel`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to cancel review task');
    }
  },

  // ============== Review Result Items ==============
  getResult: async (resultId: string): Promise<ReviewResult> => {
    const res = await fetch(`${API_BASE}/results/${resultId}`);
    if (!res.ok) throw new Error('Failed to fetch result');
    return res.json();
  },

  updateResult: async (resultId: string, data: {
    result_code?: string;
    reasoning?: string;
    evidence?: string;
    suggestion?: string;
  }): Promise<ReviewResult> => {
    const res = await fetch(`${API_BASE}/results/${resultId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update result');
    }
    return res.json();
  },

  deleteResult: async (resultId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/results/${resultId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to delete result');
    }
  },

  // ============== Summary PDF Report ==============
  downloadSummaryPdf: async (taskId: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}/summary-pdf`);
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
    const res = await fetch(`${API_BASE}/reviews/${taskId}`);
    if (!res.ok) throw new Error('Failed to fetch task status');
    return res.json();
  },
  getResults: async (taskId: string): Promise<ReviewResult[]> => {
    const res = await fetch(`${API_BASE}/reviews/${taskId}/results`);
    if (!res.ok) throw new Error('Failed to fetch results');
    return res.json();
  }
};