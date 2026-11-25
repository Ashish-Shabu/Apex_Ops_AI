import React from 'react';
import { Plus, ExternalLink, Activity, Sparkles, AlertCircle } from 'lucide-react';
import { HealthStatus } from '../../types';

interface HeaderProps {
  currentTab: string;
  health: HealthStatus | null;
  onNewEnquiry: () => void;
}

export const Header: React.FC<HeaderProps> = ({ currentTab, health, onNewEnquiry }) => {
  const titles: Record<string, { title: string; subtitle: string }> = {
    dashboard: {
      title: 'Operations Overview',
      subtitle: 'Real-time customer enquiries, triage workload, and automation metrics',
    },
    enquiries: {
      title: 'Customer Enquiry Inbox',
      subtitle: 'Review, triage, generate AI response drafts, and approve customer communications',
    },
    knowledge: {
      title: 'Knowledge Base & RAG Index',
      subtitle: 'Upload documents, inspect extracted vector chunks, and test semantic retrieval',
    },
    orders: {
      title: 'Order Lookup & Tool Inspector',
      subtitle: 'Live order database and controlled LLM tool calling test workbench',
    },
    audit: {
      title: 'Compliance & Audit History',
      subtitle: 'Verifiable audit log of all customer enquiries, AI classifications, and staff approvals',
    },
  };

  const currentInfo = titles[currentTab] || {
    title: 'AI Operations Assistant',
    subtitle: 'Customer Support Management',
  };

  const isDemo = health?.demo_mode ?? true;

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between flex-shrink-0 z-10">
      <div>
        <h1 className="text-lg font-bold text-slate-900 leading-tight">
          {currentInfo.title}
        </h1>
        <p className="text-xs text-slate-500 hidden sm:block">
          {currentInfo.subtitle}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/* Mode Indicator Pill (Requirement 5 Compliance) */}
        {isDemo ? (
          <div 
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-300"
            title="External OpenAI API key is unset. The system is operating in Deterministic Demo Mode with verified, reproducible responses."
          >
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
            <span>Demo Mode (Deterministic AI)</span>
          </div>
        ) : (
          <div 
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-300"
            title={`Connected to Live LLM: ${health?.llm_engine}`}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Live LLM Connected</span>
          </div>
        )}

        {/* API Docs Link */}
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
        >
          <span>Swagger API</span>
          <ExternalLink className="w-3 h-3" />
        </a>

        {/* New Enquiry Button */}
        <button
          onClick={onNewEnquiry}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Enquiry</span>
        </button>
      </div>
    </header>
  );
};
