import React from 'react';
import { Rule, RiskLevel, ReviewType } from '../types';
import { Check, X, Trash2, Edit2 } from 'lucide-react';

// Valid options for dropdowns - keeping in sync with RuleManager or importing if shared constant
// Since they were defined constantly in RuleManager, I should probably move them to types or constants.
// For now duplication is acceptable or I'll just hardcode them in select.
const REVIEW_TYPES = ['内容完整性', '计算结果准确性', '禁止条款', '前后逻辑一致性', '措施遵从性', '计算正确性'];
const RISK_LEVELS = ['低风险', '中风险', '高风险'];

interface RuleTableRowProps {
  rule: Rule;
  isEditing: boolean;
  editRuleData: Partial<Rule>;
  widths: {
    clause_number: number;
    standard_name: number;
    content: number;
    review_type: number;
    risk_level: number;
    actions: number;
  };
  onStartEdit: (rule: Rule) => void;
  onCancelEdit: () => void;
  onSaveEdit: (ruleId: string) => void;
  onDeleteRule: (ruleId: string) => void;
  onEditChange: (data: Partial<Rule>) => void;
}

const RuleTableRow: React.FC<RuleTableRowProps> = React.memo(({
  rule,
  isEditing,
  editRuleData,
  widths,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onDeleteRule,
  onEditChange
}) => {
  
  if (isEditing) {
    return (
      <tr className="hover:bg-slate-50 transition-colors group">
        <td className="px-4 py-2">
          <input 
            className="w-full text-sm border rounded px-2 py-1" 
            value={editRuleData.clause_number || ''} 
            onChange={e => onEditChange({ ...editRuleData, clause_number: e.target.value })} 
          />
        </td>
        <td className="px-4 py-2">
          <input 
            className="w-full text-sm border rounded px-2 py-1" 
            value={editRuleData.standard_name || ''} 
            onChange={e => onEditChange({ ...editRuleData, standard_name: e.target.value })} 
          />
        </td>
        <td className="px-4 py-2">
          <textarea 
            className="w-full text-sm border rounded px-2 py-1 min-h-[60px]" 
            value={editRuleData.content || ''} 
            onChange={e => onEditChange({ ...editRuleData, content: e.target.value })} 
          />
        </td>
        <td className="px-4 py-2">
          <select 
            className="w-full text-xs border rounded px-1 py-1" 
            value={editRuleData.review_type || ''} 
            onChange={e => onEditChange({ ...editRuleData, review_type: e.target.value })}
          >
            {REVIEW_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </td>
        <td className="px-4 py-2">
          <select 
            className="w-full text-xs border rounded px-1 py-1" 
            value={editRuleData.risk_level || ''} 
            onChange={e => onEditChange({ ...editRuleData, risk_level: e.target.value })}
          >
            {RISK_LEVELS.map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </td>
        <td className="px-4 py-2">
          <div className="flex gap-1">
            <button onClick={() => onSaveEdit(rule.id)} className="p-1 text-green-600 hover:bg-green-100 rounded"><Check className="w-4 h-4" /></button>
            <button onClick={onCancelEdit} className="p-1 text-slate-400 hover:bg-slate-100 rounded"><X className="w-4 h-4" /></button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="hover:bg-slate-50 transition-colors group">
      <td className="px-4 py-3 align-top font-mono text-xs font-medium text-slate-600">{rule.clause_number}</td>
      <td className="px-4 py-3 align-top text-xs text-slate-500">{rule.standard_name || '-'}</td>
      <td className="px-4 py-3 align-top text-slate-700 leading-relaxed">{rule.content}</td>
      <td className="px-4 py-3 align-top">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100">
          {rule.review_type || '-'}
        </span>
      </td>
      <td className="px-4 py-3 align-top">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border
          ${rule.risk_level === '高风险' ? 'bg-red-50 text-red-700 border-red-100' :
            rule.risk_level === '中风险' ? 'bg-amber-50 text-amber-700 border-amber-100' :
              'bg-slate-50 text-slate-600 border-slate-100'}`}>
          {rule.risk_level}
        </span>
      </td>
      <td className="px-4 py-3 align-top">
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onDeleteRule(rule.id)} className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded">
            <Trash2 className="w-4 h-4" />
          </button>
          <button onClick={() => onStartEdit(rule)} className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded">
            <Edit2 className="w-4 h-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}, (prevProps, nextProps) => {
  // Custom comparator
  
  // If rule object changed
  if (prevProps.rule !== nextProps.rule) return false;
  
  // If editing state changed
  if (prevProps.isEditing !== nextProps.isEditing) return false;
  
  // If widths changed (affects layout mainly in header, but if we used widths here... wait)
  // The widths prompt passed in props is NOT USED in the <tr> or <td> styles in the implementation above!
  // In RuleManager.tsx, only the TH used "style={{ width: widths.foo }}". 
  // The TD cells did NOT use widths. They rely on the table layout matching headers.
  // EXCEPT: the TH uses width. Table layout 'fixed' might enforce it.
  // If standard HTML table, TDs follow THs.
  // RuleTableRow doesn't actually CONSUME `widths` prop in rendering?
  // Let's re-read the code I just wrote.
  // Yes, I didn't use `widths` in `RuleTableRow`.
  // So `widths` prop changes should NOT trigger re-render of rows if rows don't use it.
  // BUT I included it in props.
  // So I should ignore it in comparator unless I actually use it.
  
  // If being edited, check editData
  if (nextProps.isEditing) {
    if (prevProps.editRuleData !== nextProps.editRuleData) return false;
  }
  
  return true; 
});

export default RuleTableRow;