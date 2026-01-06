import React from 'react';
import { ShieldCheck, FileText, Play, BarChart3, History } from 'lucide-react';
import { AppStep } from '../types';

interface LayoutProps {
  currentStep: AppStep;
  onNavigate: (step: AppStep) => void;
  children: React.ReactNode;
}

const steps = [
  { id: AppStep.Rules, label: '规则管理', icon: ShieldCheck },
  { id: AppStep.Comparison, label: '对比文件', icon: FileText },
  { id: AppStep.Upload, label: '文档仓库', icon: FileText },
  { id: AppStep.Review, label: '启动审查', icon: Play },
  { id: AppStep.Report, label: '审查结果', icon: BarChart3 },
  { id: AppStep.HistoryAnalysis, label: '对比分析', icon: History },
];

export const Layout: React.FC<LayoutProps> = ({ currentStep, onNavigate, children }) => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">智能文档审查系统</h1>
              <p className="text-xs text-slate-500 font-medium">ADS Lite - 自动化工程报告审查</p>
            </div>
          </div>
          <nav className="hidden md:flex space-x-2">
            {steps.map((step) => {
              const Icon = step.icon;
              const isActive = currentStep === step.id;

              return (
                <button
                  key={step.id}
                  onClick={() => onNavigate(step.id)}
                  className={`
                    flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    ${isActive
                      ? 'bg-indigo-50 text-indigo-700 shadow-sm border border-indigo-100'
                      : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                    }
                  `}
                >
                  <Icon className={`w-4 h-4 mr-2 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
                  {step.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      <footer className="bg-white border-t border-slate-200 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-slate-400">
          基于 DeepSeek AI 大模型 • 智能文档审查系统
        </div>
      </footer>
    </div>
  );
};