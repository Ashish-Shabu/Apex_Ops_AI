import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  Sparkles, 
  Bot, 
  FileText, 
  Wrench, 
  ChevronRight, 
  Send, 
  X, 
  Edit3, 
  RefreshCw,
  Package,
  User,
  Mail,
  ShieldAlert,
  ArrowUpRight
} from 'lucide-react';
import { Enquiry, EnquiryDetail, ResponseDraft, EnquiryStatus, EnquiryCategory } from '../../types';
import { api } from '../../services/api';

interface EnquiriesViewProps {
  onRefreshStats: () => void;
  onNavigateOrder?: (orderNum: string) => void;
}

export const EnquiriesView: React.FC<EnquiriesViewProps> = ({ onRefreshStats, onNavigateOrder }) => {
  const [enquiries, setEnquiries] = useState<Enquiry[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedEnquiry, setSelectedEnquiry] = useState<EnquiryDetail | null>(null);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // AI draft states
  const [generatingDraft, setGeneratingDraft] = useState<boolean>(false);
  const [reclassifying, setReclassifying] = useState<boolean>(false);
  const [staffNotes, setStaffNotes] = useState<string>('');
  const [editedDraftText, setEditedDraftText] = useState<string>('');
  const [reviewFeedback, setReviewFeedback] = useState<string>('');
  const [reviewingAction, setReviewingAction] = useState<boolean>(false);
  const [showSources, setShowSources] = useState<boolean>(true);

  // Load enquiries
  const loadEnquiries = async () => {
    setLoadingList(true);
    try {
      const params: any = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (categoryFilter !== 'all') params.category = categoryFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const data = await api.getEnquiries(params);
      setEnquiries(data);

      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      } else if (data.length === 0) {
        setSelectedId(null);
        setSelectedEnquiry(null);
      }
    } catch (err) {
      console.error('Failed to load enquiries:', err);
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    loadEnquiries();
  }, [statusFilter, categoryFilter]);

  // Debounced search
  useEffect(() => {
    const handler = setTimeout(() => {
      loadEnquiries();
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Load single enquiry details
  const loadDetail = async (id: number) => {
    setLoadingDetail(true);
    try {
      const data = await api.getEnquiry(id);
      setSelectedEnquiry(data);
      if (data.drafts && data.drafts.length > 0) {
        setEditedDraftText(data.drafts[0].draft_body);
      } else {
        setEditedDraftText('');
      }
    } catch (err) {
      console.error('Failed to load enquiry detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    if (selectedId) {
      loadDetail(selectedId);
    }
  }, [selectedId]);

  // Generate AI Draft
  const handleGenerateDraft = async () => {
    if (!selectedId) return;
    setGeneratingDraft(true);
    try {
      const draft = await api.generateDraft(selectedId, staffNotes);
      await loadDetail(selectedId);
      await loadEnquiries();
      onRefreshStats();
      setStaffNotes('');
    } catch (err) {
      console.error('Draft generation failed:', err);
      alert('Failed to generate draft. Please check server logs.');
    } finally {
      setGeneratingDraft(false);
    }
  };

  // Re-classify
  const handleReclassify = async () => {
    if (!selectedId) return;
    setReclassifying(true);
    try {
      await api.reclassifyEnquiry(selectedId);
      await loadDetail(selectedId);
      await loadEnquiries();
      onRefreshStats();
    } catch (err) {
      console.error('Re-classify failed:', err);
    } finally {
      setReclassifying(false);
    }
  };

  // Review Draft (Approve / Reject)
  const handleReviewDraft = async (action: 'approved' | 'rejected' | 'edited_and_approved') => {
    if (!selectedId || !selectedEnquiry || !selectedEnquiry.drafts.length) return;
    setReviewingAction(true);
    try {
      const latestDraft = selectedEnquiry.drafts[0];
      await api.reviewDraft(selectedId, latestDraft.id, {
        status: action,
        edited_draft_body: action === 'edited_and_approved' ? editedDraftText : undefined,
        reviewed_by: 'Staff Specialist Clara',
        review_feedback: reviewFeedback || undefined,
      });
      await loadDetail(selectedId);
      await loadEnquiries();
      onRefreshStats();
      setReviewFeedback('');
    } catch (err) {
      console.error('Draft review failed:', err);
      alert('Failed to update draft review.');
    } finally {
      setReviewingAction(false);
    }
  };

  const getStatusBadge = (status: EnquiryStatus) => {
    switch (status) {
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <Clock className="w-3 h-3 text-slate-500" />
            <span>Pending</span>
          </span>
        );
      case 'in_review':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
            <RefreshCw className="w-3 h-3 text-blue-500" />
            <span>In Review</span>
          </span>
        );
      case 'awaiting_approval':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-300">
            <AlertCircle className="w-3 h-3 text-amber-600" />
            <span>Awaiting Approval</span>
          </span>
        );
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            <span>Resolved</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <X className="w-3 h-3 text-rose-500" />
            <span>Rejected</span>
          </span>
        );
    }
  };

  const getCategoryLabel = (cat: string) => {
    const map: Record<string, string> = {
      order_status: 'Order Status',
      delivery: 'Delivery',
      refund_return: 'Refund / Return',
      company_policy: 'Company Policy',
      general_support: 'General Support',
    };
    return map[cat] || cat;
  };

  const latestDraft = selectedEnquiry?.drafts?.[0];

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-50">
      {/* ----------------- LEFT PANE: ENQUIRY LIST (380px) ----------------- */}
      <div className="w-[380px] bg-white border-r border-slate-200 flex flex-col flex-shrink-0">
        {/* Search & Filters */}
        <div className="p-3.5 border-b border-slate-200 space-y-2.5">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search enquiries, orders, email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:bg-white"
            />
          </div>

          {/* Status Pills */}
          <div className="flex gap-1 overflow-x-auto pb-1 text-[11px]">
            {['all', 'pending', 'awaiting_approval', 'resolved'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2.5 py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  statusFilter === s
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {s === 'all'
                  ? 'All'
                  : s === 'awaiting_approval'
                  ? 'Awaiting Approval'
                  : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Enquiry Item Cards */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {loadingList ? (
            <div className="p-6 text-center text-xs text-slate-400">Loading enquiries...</div>
          ) : enquiries.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">
              No customer enquiries found matching criteria.
            </div>
          ) : (
            enquiries.map((enq) => {
              const isSelected = enq.id === selectedId;
              return (
                <div
                  key={enq.id}
                  onClick={() => setSelectedId(enq.id)}
                  className={`p-3.5 cursor-pointer transition-colors border-l-4 ${
                    isSelected
                      ? 'bg-indigo-50/50 border-indigo-600'
                      : 'hover:bg-slate-50/80 border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-semibold text-slate-900 truncate">
                      {enq.customer_name}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono whitespace-nowrap">
                      {new Date(enq.created_at).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                  </div>

                  <p className="text-xs text-slate-700 font-medium truncate mb-1.5">
                    {enq.subject}
                  </p>

                  <div className="flex items-center justify-between gap-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                        {getCategoryLabel(enq.category)}
                      </span>
                      {enq.order_number && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 font-mono font-medium">
                          {enq.order_number}
                        </span>
                      )}
                    </div>
                    {getStatusBadge(enq.status)}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ----------------- RIGHT PANE: ENQUIRY DETAILS & DRAFT REVIEW ----------------- */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {!selectedEnquiry ? (
          <div className="flex-1 flex items-center justify-center p-8 text-slate-400 text-xs">
            Select a customer enquiry from the inbox to inspect and review drafts.
          </div>
        ) : (
          <div className="p-6 max-w-5xl mx-auto w-full space-y-6">
            {/* Header: Title, Customer, Order & Status */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-slate-400">
                      TICKET #{selectedEnquiry.id}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                      Channel: {selectedEnquiry.channel}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 leading-snug">
                    {selectedEnquiry.subject}
                  </h2>
                </div>
                <div>{getStatusBadge(selectedEnquiry.status)}</div>
              </div>

              {/* Customer and Order Metas */}
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 pt-3 border-t border-slate-100">
                <div className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span className="font-semibold text-slate-800">
                    {selectedEnquiry.customer_name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-slate-600">{selectedEnquiry.customer_email}</span>
                </div>
                {selectedEnquiry.order_number && (
                  <div className="flex items-center gap-1.5 bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-mono font-medium">
                    <Package className="w-3.5 h-3.5 text-indigo-500" />
                    <span>Order: {selectedEnquiry.order_number}</span>
                  </div>
                )}
                <div className="ml-auto text-[11px] text-slate-400">
                  Received: {new Date(selectedEnquiry.created_at).toLocaleString()}
                </div>
              </div>
            </div>

            {/* Customer Message Body */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Customer Message
              </h3>
              <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed bg-slate-50/70 p-4 rounded-lg border border-slate-200/60 font-sans">
                {selectedEnquiry.message}
              </p>
            </div>

            {/* AI Classification & Structured Summary Card */}
            <div className="bg-gradient-to-r from-indigo-50/70 via-purple-50/40 to-slate-50 rounded-xl border border-indigo-100 p-5 shadow-xs">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md bg-indigo-600 text-white flex items-center justify-center">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <h3 className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                    AI Intent Classification & Summary
                  </h3>
                </div>
                <button
                  onClick={handleReclassify}
                  disabled={reclassifying}
                  className="flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${reclassifying ? 'animate-spin' : ''}`} />
                  <span>{reclassifying ? 'Analyzing...' : 'Re-classify'}</span>
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3 text-xs">
                <div className="bg-white/80 p-2.5 rounded-lg border border-indigo-100/60">
                  <span className="text-[10px] text-slate-500 block">Classified Category</span>
                  <span className="font-semibold text-slate-900 capitalize">
                    {getCategoryLabel(selectedEnquiry.category)}
                  </span>
                </div>
                <div className="bg-white/80 p-2.5 rounded-lg border border-indigo-100/60">
                  <span className="text-[10px] text-slate-500 block">Priority Level</span>
                  <span className="font-semibold text-slate-900 capitalize">
                    {selectedEnquiry.priority}
                  </span>
                </div>
                <div className="bg-white/80 p-2.5 rounded-lg border border-indigo-100/60">
                  <span className="text-[10px] text-slate-500 block">Customer Sentiment</span>
                  <span className="font-semibold text-slate-900 capitalize">
                    {selectedEnquiry.sentiment}
                  </span>
                </div>
                <div className="bg-white/80 p-2.5 rounded-lg border border-indigo-100/60">
                  <span className="text-[10px] text-slate-500 block">AI Confidence</span>
                  <span className="font-semibold text-indigo-700">
                    {Math.round(selectedEnquiry.ai_confidence * 100)}%
                  </span>
                </div>
              </div>

              {selectedEnquiry.ai_summary && (
                <div className="bg-white/90 p-3 rounded-lg border border-indigo-100/80 text-xs">
                  <span className="font-semibold text-indigo-900 block mb-0.5">Summary:</span>
                  <p className="text-slate-700 leading-relaxed">{selectedEnquiry.ai_summary}</p>
                </div>
              )}
            </div>

            {/* AI Response Draft Workspace (Requirement 3.F) */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Bot className="w-5 h-5 text-indigo-600" />
                  <h3 className="text-sm font-bold text-slate-900">
                    AI Response Draft & Review
                  </h3>
                </div>

                {latestDraft && (
                  <span
                    className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${
                      latestDraft.status === 'approved' || latestDraft.status === 'edited_and_approved'
                        ? 'bg-emerald-100 text-emerald-800'
                        : latestDraft.status === 'rejected'
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    Draft Status: {latestDraft.status.replace(/_/g, ' ').toUpperCase()}
                  </span>
                )}
              </div>

              {/* RAG & Tool Execution Badges */}
              {latestDraft && (
                <div className="space-y-3">
                  {/* Order-Product Mismatch Alert Banner (Internal Staff Only) */}
                  {latestDraft.order_product_mismatch && (
                    <div className="p-3.5 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg text-xs text-amber-950 shadow-sm space-y-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 font-bold text-amber-900">
                          <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0" />
                          <span>INTERNAL STAFF WARNING: Order-Product Mismatch</span>
                        </div>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-200/80 text-amber-900">
                          Privacy Protected
                        </span>
                      </div>
                      <p className="text-amber-800 leading-relaxed">
                        {latestDraft.mismatch_details?.reason ||
                          "Customer enquiry product does not match the items registered in this order."}
                      </p>
                      {latestDraft.mismatch_details?.order_actual_products &&
                        latestDraft.mismatch_details.order_actual_products.length > 0 && (
                          <div className="pt-1.5 border-t border-amber-200/60 text-[11px] text-amber-900 flex flex-col gap-0.5">
                            <div>
                              <span className="font-semibold">Registered Order Items (Internal Only): </span>
                              <span className="font-mono bg-white/70 px-1.5 py-0.5 rounded border border-amber-200">
                                {latestDraft.mismatch_details.order_actual_products.join(', ')}
                              </span>
                            </div>
                            <p className="text-[10px] text-amber-700 italic mt-0.5">
                              Customer-facing draft has been sanitized to preserve privacy. It asks the customer to verify order and checkout details without revealing the actual registered items.
                            </p>
                          </div>
                        )}
                    </div>
                  )}

                  {/* Tool Calls Used */}
                  {latestDraft.tool_calls_used && latestDraft.tool_calls_used.length > 0 && (
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80 text-xs">
                      <div className="flex items-center gap-1.5 font-semibold text-slate-700 mb-2">
                        <Wrench className="w-3.5 h-3.5 text-indigo-600" />
                        <span>Backend Tool Calling Invocations:</span>
                      </div>
                      <div className="space-y-1.5">
                        {latestDraft.tool_calls_used.map((tool, idx) => (
                          <div
                            key={idx}
                            className="bg-white p-2 rounded border border-slate-200 flex items-center justify-between font-mono text-[11px]"
                          >
                            <span className="text-indigo-700 font-semibold">
                              {tool.tool_name}({JSON.stringify(tool.arguments)})
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] ${
                                tool.result?.found
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              {tool.result?.found
                                ? `Order Status: ${tool.result.order?.status?.toUpperCase()}`
                                : 'Executed'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Retrieved Sources Accordion */}
                  {latestDraft.retrieved_sources && latestDraft.retrieved_sources.length > 0 && (
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80 text-xs">
                      <button
                        onClick={() => setShowSources(!showSources)}
                        className="w-full flex items-center justify-between text-left font-semibold text-slate-700"
                      >
                        <div className="flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-indigo-600" />
                          <span>
                            Grounded in {latestDraft.retrieved_sources.length} Knowledge Base Source
                            {latestDraft.retrieved_sources.length > 1 ? 's' : ''}
                          </span>
                        </div>
                        <span className="text-[11px] text-indigo-600 hover:underline">
                          {showSources ? 'Hide Sources' : 'Show Sources'}
                        </span>
                      </button>

                      {showSources && (
                        <div className="mt-2.5 space-y-2">
                          {latestDraft.retrieved_sources.map((src, i) => (
                            <div
                              key={i}
                              className="bg-white p-2.5 rounded border border-slate-200 text-xs"
                            >
                              <div className="flex items-center justify-between font-semibold text-slate-800 mb-1">
                                <span>
                                  📄 {src.document_title} (Chunk #{src.chunk_index})
                                </span>
                                {src.similarity_score !== undefined && (
                                  <span className="text-[10px] font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.2 rounded">
                                    Sim: {(src.similarity_score * 100).toFixed(1)}%
                                  </span>
                                )}
                              </div>
                              {src.content && (
                                <p className="text-slate-600 text-[11px] italic bg-slate-50 p-2 rounded border border-slate-100">
                                  "{src.content}"
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Rationale explanation */}
                  {latestDraft.rationale && (
                    <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100 text-xs">
                      <span className="font-semibold text-indigo-950 block mb-0.5">
                        AI Reasoning & Grounding Rationale:
                      </span>
                      <p className="text-slate-700 text-[11px] leading-relaxed">
                        {latestDraft.rationale}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Draft Body Text Area */}
              {latestDraft ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-700 flex items-center gap-1.5">
                      <Edit3 className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Draft Customer Response (Editable by Staff)</span>
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      Staff must review and approve prior to sending
                    </span>
                  </div>

                  <textarea
                    rows={10}
                    value={editedDraftText}
                    onChange={(e) => setEditedDraftText(e.target.value)}
                    disabled={
                      latestDraft.status === 'approved' || latestDraft.status === 'edited_and_approved'
                    }
                    className="w-full p-3.5 text-xs font-mono text-slate-800 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 leading-relaxed disabled:bg-slate-50 disabled:text-slate-600"
                  />

                  {/* Staff Review Actions */}
                  {latestDraft.status === 'pending_review' ? (
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Internal review feedback / notes (optional)..."
                          value={reviewFeedback}
                          onChange={(e) => setReviewFeedback(e.target.value)}
                          className="flex-1 px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        />
                      </div>

                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button
                          onClick={() => handleReviewDraft('rejected')}
                          disabled={reviewingAction}
                          className="px-3.5 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Reject Draft</span>
                        </button>

                        <button
                          onClick={() => handleReviewDraft('edited_and_approved')}
                          disabled={reviewingAction}
                          className="px-3.5 py-2 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Save Edits & Approve</span>
                        </button>

                        <button
                          onClick={() => handleReviewDraft('approved')}
                          disabled={reviewingAction}
                          className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors shadow-xs flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve & Mark Resolved</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>
                          Reviewed & Approved by{' '}
                          <strong>{latestDraft.reviewed_by || 'Staff'}</strong> on{' '}
                          {latestDraft.reviewed_at
                            ? new Date(latestDraft.reviewed_at).toLocaleString()
                            : ''}
                        </span>
                      </div>
                      <button
                        onClick={handleGenerateDraft}
                        disabled={generatingDraft}
                        className="text-xs text-indigo-600 hover:underline font-semibold"
                      >
                        Generate New Draft Version
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                /* No draft generated yet */
                <div className="py-8 text-center space-y-4 bg-slate-50 rounded-xl border border-dashed border-slate-300 p-6">
                  <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center mx-auto">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-800">
                      No Response Draft Generated Yet
                    </h4>
                    <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                      Click below to let the AI search the Knowledge Base (RAG), check order status
                      via backend tools, and assemble a grounded draft.
                    </p>
                  </div>

                  <div className="max-w-md mx-auto">
                    <input
                      type="text"
                      placeholder="Optional staff notes to guide the draft..."
                      value={staffNotes}
                      onChange={(e) => setStaffNotes(e.target.value)}
                      className="w-full mb-3 px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 text-center"
                    />

                    <button
                      onClick={handleGenerateDraft}
                      disabled={generatingDraft}
                      className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all flex items-center gap-2 mx-auto disabled:opacity-50"
                    >
                      <Sparkles className={`w-4 h-4 ${generatingDraft ? 'animate-spin' : ''}`} />
                      <span>
                        {generatingDraft
                          ? 'Generating Context-Aware Draft...'
                          : 'Generate AI Response Draft'}
                      </span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Audit History Timeline for this Enquiry */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
                Ticket Activity & Audit Trail
              </h3>

              <div className="space-y-3">
                {selectedEnquiry.audit_logs?.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-start gap-3 text-xs pb-3 border-b border-slate-100 last:border-0 last:pb-0"
                  >
                    <div className="w-2 h-2 rounded-full bg-indigo-600 mt-1.5 flex-shrink-0"></div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800 capitalize">
                          {log.action.replace(/_/g, ' ')}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <span className="text-slate-500 text-[11px]">Actor: {log.actor}</span>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <pre className="mt-1 p-2 bg-slate-50 rounded text-[10px] text-slate-600 overflow-x-auto font-mono">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
