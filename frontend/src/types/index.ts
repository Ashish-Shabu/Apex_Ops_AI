export type EnquiryStatus = 'pending' | 'in_review' | 'awaiting_approval' | 'resolved' | 'rejected';

export type EnquiryCategory = 
  | 'order_status' 
  | 'delivery' 
  | 'refund_return' 
  | 'company_policy' 
  | 'general_support';

export type EnquiryPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Enquiry {
  id: number;
  customer_name: str;
  customer_email: str;
  channel: string;
  subject: string;
  message: string;
  category: EnquiryCategory;
  status: EnquiryStatus;
  priority: EnquiryPriority;
  sentiment: string;
  ai_summary: string | null;
  ai_confidence: number;
  order_number: string | null;
  created_at: string;
  updated_at: string;
  drafts_count: number;
  latest_draft_id: number | null;
}

export type str = string;

export interface ResponseDraft {
  id: number;
  enquiry_id: number;
  draft_body: string;
  rationale: string | null;
  retrieved_sources: Array<{
    document_id?: number;
    document_title: string;
    chunk_index: number;
    similarity_score?: number;
    content?: string;
  }>;
  tool_calls_used: Array<{
    tool_name: string;
    arguments: Record<string, any>;
    result: any;
    success?: boolean;
  }>;
  status: 'pending_review' | 'approved' | 'rejected' | 'edited_and_approved';
  order_product_mismatch?: boolean;
  mismatch_details?: Record<string, any>;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: number;
  enquiry_id: number | null;
  action: string;
  actor: string;
  details: Record<string, any>;
  created_at: string;
}

export interface EnquiryDetail extends Enquiry {
  drafts: ResponseDraft[];
  audit_logs: AuditLog[];
}

export interface DocumentItem {
  id: number;
  title: string;
  file_name: string;
  file_type: string;
  file_size_bytes: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: number;
  document_id: number;
  chunk_index: number;
  content: string;
  metadata_info: Record<string, any>;
  created_at: string;
}

export interface DocumentDetail extends DocumentItem {
  chunks: DocumentChunk[];
}

export interface SearchResultItem {
  document_id: number;
  document_title: string;
  chunk_id: number;
  chunk_index: number;
  content: string;
  similarity_score: number;
}

export interface OrderItem {
  id: number;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

export interface Order {
  id: number;
  order_number: string;
  customer_name: string;
  customer_email: string;
  status: string;
  total_amount: number;
  currency: string;
  tracking_number: string | null;
  carrier: string | null;
  shipping_address: string;
  order_date: string;
  estimated_delivery: string | null;
  delivered_at: string | null;
  items: OrderItem[];
}

export interface DashboardStats {
  total_enquiries: number;
  pending_enquiries: number;
  awaiting_approval_enquiries: number;
  resolved_enquiries: number;
  categories_breakdown: Record<string, number>;
  priorities_breakdown: Record<string, number>;
  total_documents: number;
  total_chunks: number;
  recent_activity: AuditLog[];
}

export interface HealthStatus {
  status: string;
  service: string;
  environment: string;
  demo_mode: boolean;
  llm_engine: string;
  docs_url: string;
}
