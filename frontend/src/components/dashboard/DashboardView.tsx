import React from 'react';
import { 
  Inbox, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  BookOpen, 
  ArrowRight,
  TrendingUp,
  Activity,
  Layers
} from 'lucide-react';
import { DashboardStats } from '../../types';

interface DashboardViewProps {
  stats: DashboardStats | null;
  loading: boolean;
  onNavigate: (tab: string) => void;
  onNewEnquiry: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  stats,
  loading,
  onNavigate,
  onNewEnquiry,
}) => {
  if (loading || !stats) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-slate-500 font-medium">Loading operations metrics...</p>
        </div>
      </div>
    );
  }

  const categoryLabels: Record<string, string> = {
    order_status: 'Order Status',
    delivery: 'Delivery & Shipping',
    refund_return: 'Refunds & Returns',
    company_policy: 'Company Policy',
    general_support: 'General Support',
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Banner Alert for Awaiting Approval */}
      {stats.awaiting_approval_enquiries > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center text-amber-700">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-amber-900">
                {stats.awaiting_approval_enquiries} AI Draft{stats.awaiting_approval_enquiries > 1 ? 's' : ''} Awaiting Staff Approval
              </h4>
              <p className="text-xs text-amber-700">
                Responses have been generated using RAG and backend order lookups. Review and approve before sending.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate('enquiries')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors"
          >
            <span>Review Drafts</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Enquiries */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Enquiries</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{stats.total_enquiries}</h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">All incoming tickets</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">
            <Inbox className="w-6 h-6" />
          </div>
        </div>

        {/* Pending Triage */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Pending Triage</p>
            <h3 className="text-2xl font-bold text-indigo-600 mt-1">{stats.pending_enquiries}</h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Requires draft generation</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        {/* Awaiting Staff Approval */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Awaiting Approval</p>
            <h3 className="text-2xl font-bold text-amber-600 mt-1">{stats.awaiting_approval_enquiries}</h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">AI draft ready for review</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        {/* Resolved */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Resolved</p>
            <h3 className="text-2xl font-bold text-emerald-600 mt-1">{stats.resolved_enquiries}</h3>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Approved & dispatched</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Middle Row: Category Breakdown & Knowledge Index Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Category Breakdown (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Enquiry Categories</h3>
              <p className="text-xs text-slate-500">Breakdown of customer intent classified by AI</p>
            </div>
            <button
              onClick={() => onNavigate('enquiries')}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-3">
            {Object.entries(stats.categories_breakdown).length === 0 ? (
              <p className="text-xs text-slate-400 italic py-4">No enquiries recorded yet.</p>
            ) : (
              Object.entries(stats.categories_breakdown).map(([category, count]) => {
                const percentage = stats.total_enquiries > 0 
                  ? Math.round((count / stats.total_enquiries) * 100) 
                  : 0;
                return (
                  <div key={category} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-700">
                        {categoryLabels[category] || category}
                      </span>
                      <span className="text-slate-500">
                        {count} ({percentage}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Knowledge Base & RAG Stats (1 Col) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900">RAG Vector Index</h3>
              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <BookOpen className="w-4 h-4" />
              </div>
            </div>

            <p className="text-xs text-slate-500 mb-4">
              Company policy documents are vectorized and indexed for cosine similarity RAG retrieval.
            </p>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/60 text-center">
                <p className="text-[11px] font-medium text-slate-500">Documents</p>
                <p className="text-xl font-bold text-slate-900 mt-0.5">{stats.total_documents}</p>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/60 text-center">
                <p className="text-[11px] font-medium text-slate-500">Vector Chunks</p>
                <p className="text-xl font-bold text-indigo-600 mt-0.5">{stats.total_chunks}</p>
              </div>
            </div>
          </div>

          <button
            onClick={() => onNavigate('knowledge')}
            className="w-full py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-colors"
          >
            <span>Manage Knowledge Base</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Bottom Section: Recent Operations Activity Feed */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Recent Operations Activity</h3>
            <p className="text-xs text-slate-500">Audit trail of customer tickets, AI actions, and staff decisions</p>
          </div>
          <button
            onClick={() => onNavigate('audit')}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            <span>Full Audit Log</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-100">
          {stats.recent_activity.length === 0 ? (
            <p className="text-xs text-slate-400 italic py-4">No recent activity logged.</p>
          ) : (
            stats.recent_activity.map((activity) => (
              <div key={activity.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-indigo-500 flex-shrink-0"></span>
                  <div>
                    <span className="font-semibold text-slate-800 capitalize">
                      {activity.action.replace(/_/g, ' ')}
                    </span>
                    <span className="text-slate-400 mx-1.5">•</span>
                    <span className="text-slate-500">by {activity.actor}</span>
                    {activity.enquiry_id && (
                      <span className="ml-2 text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded text-[10px] font-mono">
                        Ticket #{activity.enquiry_id}
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-[11px] text-slate-400 flex-shrink-0 font-mono">
                  {new Date(activity.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
