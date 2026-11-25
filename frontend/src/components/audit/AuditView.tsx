import React, { useState, useEffect } from 'react';
import { History, Shield, Filter, Search, ChevronDown, ChevronUp } from 'lucide-react';
import { AuditLog } from '../../types';
import { api } from '../../services/api';

export const AuditView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actionFilter, setActionFilter] = useState<string>('all');

  const loadAuditLogs = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditLogs(
        undefined,
        actionFilter !== 'all' ? actionFilter : undefined
      );
      setLogs(data);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [actionFilter]);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getActorBadge = (actor: string) => {
    if (actor.startsWith('ai_') || actor === 'ai_assistant' || actor === 'ai_engine') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-100 text-purple-800 font-semibold">
          🤖 {actor}
        </span>
      );
    } else if (actor.startsWith('staff:')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-100 text-emerald-800 font-semibold">
          👤 {actor}
        </span>
      );
    } else if (actor.startsWith('customer:')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-100 text-blue-800 font-semibold">
          ✉️ {actor}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-700">
        {actor}
      </span>
    );
  };

  const getActionBadge = (action: string) => {
    const isApproval = action.includes('approved');
    const isRejection = action.includes('rejected');
    const isDraft = action.includes('draft');

    return (
      <span
        className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
          isApproval
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            : isRejection
            ? 'bg-rose-50 text-rose-700 border border-rose-200'
            : isDraft
            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
            : 'bg-slate-100 text-slate-700 border border-slate-200'
        }`}
      >
        {action.replace(/_/g, ' ').toUpperCase()}
      </span>
    );
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">Operations Audit Trail</h3>
            </div>
            <p className="text-xs text-slate-500">
              Immutable record of customer interactions, AI classifications, draft outputs, and staff authorizations.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Filter Action:</span>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="all">All Actions</option>
              <option value="enquiry_created">Enquiry Created</option>
              <option value="ai_classified">AI Classified</option>
              <option value="draft_generated">Draft Generated</option>
              <option value="draft_approved">Draft Approved</option>
              <option value="draft_rejected">Draft Rejected</option>
              <option value="document_ingested">Document Ingested</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-center text-xs text-slate-400">Loading audit records...</div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">No audit events found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px] border-y border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Event ID</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Associated Ticket</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => {
                  const isExpanded = expandedId === log.id;
                  return (
                    <React.Fragment key={log.id}>
                      <tr className="hover:bg-slate-50/80">
                        <td className="py-3 px-3 font-mono text-slate-400 text-[11px]">
                          #{log.id}
                        </td>
                        <td className="py-3 px-3">{getActionBadge(log.action)}</td>
                        <td className="py-3 px-3">{getActorBadge(log.actor)}</td>
                        <td className="py-3 px-3">
                          {log.enquiry_id ? (
                            <span className="font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded text-[11px]">
                              Ticket #{log.enquiry_id}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic text-[11px]">System-wide</span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-slate-500 font-mono text-[11px]">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => toggleExpand(log.id)}
                            className="p-1 text-slate-400 hover:text-indigo-600 transition-colors"
                          >
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 inline" />
                            ) : (
                              <ChevronDown className="w-4 h-4 inline" />
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded JSON payload */}
                      {isExpanded && (
                        <tr className="bg-slate-50">
                          <td colSpan={6} className="p-4">
                            <div className="bg-slate-900 text-indigo-200 p-3 rounded-lg text-xs font-mono overflow-x-auto">
                              <span className="text-slate-400 block mb-1">
                                Payload Metadata:
                              </span>
                              <pre>{JSON.stringify(log.details, null, 2)}</pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
