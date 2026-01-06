export enum RiskLevel {
  High = '高风险',
  Medium = '中风险',
  Low = '低风险'
}

export enum ReviewType {
  ContentCompleteness = '内容完整性',
  CalculationAccuracy = '计算结果准确性',
  ProhibitionClause = '禁止条款',
  LogicConsistency = '前后逻辑一致性',
  MeasureCompliance = '措施遵从性',
  CalculationCorrectness = '计算正确性'
}

export interface RuleGroup {
  id: string;
  name: string;
  description?: string;
  parent_id?: string;
  children?: RuleGroup[];
  created_at?: string;
}

export interface Rule {
  id: string;
  group_id: string;
  clause_number: string;  // 条文号 (如 3.1.2)
  standard_name?: string; // 来源标准名称
  content: string;        // 规则具体内容
  review_type?: string;   // 审查类型
  risk_level: string;     // 风险等级 (低风险/中风险/高风险)
}

export interface Document {
  id: string;
  filename: string;
  storage_path?: string;
  markdown_path?: string;
  mineru_batch_id?: string;
  mineru_zip_url?: string;
  status: 'UPLOADING' | 'PARSING' | 'EMBEDDING' | 'DONE' | 'FAILED';
  error_message?: string;
  meta_info?: string;
  upload_time: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  word_count: number;
  sentence_count: number;
}

export interface ReviewTask {
  id: string;
  document_id: string;
  document_name?: string;
  rule_group_id: string;
  rule_group_name?: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress: number;
  start_time?: string;
  end_time?: string;
  created_at?: string;
  stats?: {
    PASS: number;
    REJECT: number;
    MANUAL_CHECK: number;
  };
}

export type ResultCode = 'PASS' | 'REJECT' | 'MANUAL_CHECK';

export interface ReviewResult {
  id: string;
  task_id: string;
  rule_id: string;
  clause_number: string;
  standard_name?: string;  // 规则来源/规范名称
  rule_content: string;
  review_type?: string;
  risk_level?: string;
  result_code: ResultCode;
  reasoning: string | null;
  evidence: string | null;
  suggestion: string | null;
  created_at?: string;
  // Legacy field for backward compatibility
  status?: string;
}

export enum AppStep {
  Rules = 'RULES',
  Upload = 'UPLOAD',
  Review = 'REVIEW',
  Report = 'REPORT',
  HistoryAnalysis = 'HISTORY_ANALYSIS',
  Comparison = 'COMPARISON'
}

export interface HistoryAnalysisTask {
  id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  draft_filenames: string; // JSON string
  approved_filenames: string; // JSON string
  created_at: string;
}

export interface InferredOpinion {
  id: string;
  task_id: string;
  opinion: string;
  evidence: string | null;
  clause: string | null;
  risk_level: string;
  review_type?: string;
  draft_file_location?: string;  // JSON string
  approved_file_location?: string;  // JSON string
  status: 'PENDING' | 'ADDED' | 'IGNORED' | 'DELETED';
  created_at: string;
}

export interface FileLocation {
  filename: string;
  page: number;
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}


export interface UploadedFile {
  data: string;
  type: string;
}

export enum ReviewStatus {
  Pass = 'Pass',
  Fail = 'Fail',
  NotApplicable = 'N/A'
}

export interface ComparisonDocument {
  id: string;
  filename: string;
  storage_path?: string;
  markdown_path?: string;
  mineru_batch_id?: string;
  mineru_zip_url?: string;
  status: 'UPLOADING' | 'PARSING' | 'EMBEDDING' | 'DONE' | 'FAILED';
  error_message?: string;
  description?: string;
  upload_time: string;
}

export interface ComparisonResult {
  id: string;
  task_id: string;
  comparison_document_id: string;
  conflict_score: number;
  summary: string | null;
  details: string | null; // JSON string
  created_at: string;
  document_name?: string; // Enriched field
}