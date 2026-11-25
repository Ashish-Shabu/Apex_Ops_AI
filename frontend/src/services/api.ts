import axios from 'axios';
import {
  Enquiry,
  EnquiryDetail,
  ResponseDraft,
  DocumentItem,
  DocumentDetail,
  SearchResultItem,
  Order,
  DashboardStats,
  HealthStatus
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Health
  getHealth: async (): Promise<HealthStatus> => {
    const res = await axios.get('/');
    return res.data;
  },

  // Analytics
  getDashboardStats: async (): Promise<DashboardStats> => {
    const res = await apiClient.get<DashboardStats>('/analytics/dashboard');
    return res.data;
  },

  // Enquiries
  getEnquiries: async (params?: {
    status?: string;
    category?: string;
    search?: string;
  }): Promise<Enquiry[]> => {
    const res = await apiClient.get<Enquiry[]>('/enquiries', { params });
    return res.data;
  },

  getEnquiry: async (id: number): Promise<EnquiryDetail> => {
    const res = await apiClient.get<EnquiryDetail>(`/enquiries/${id}`);
    return res.data;
  },

  createEnquiry: async (data: {
    customer_name: string;
    customer_email: string;
    channel?: string;
    subject: string;
    message: string;
    order_number?: string;
  }): Promise<EnquiryDetail> => {
    const res = await apiClient.post<EnquiryDetail>('/enquiries', data);
    return res.data;
  },

  updateEnquiry: async (id: number, data: Partial<Enquiry>): Promise<EnquiryDetail> => {
    const res = await apiClient.patch<EnquiryDetail>(`/enquiries/${id}`, data);
    return res.data;
  },

  reclassifyEnquiry: async (id: number) => {
    const res = await apiClient.post(`/enquiries/${id}/classify`);
    return res.data;
  },

  generateDraft: async (id: number, staffNotes?: string): Promise<ResponseDraft> => {
    const res = await apiClient.post<ResponseDraft>(`/enquiries/${id}/draft`, {
      staff_notes: staffNotes,
    });
    return res.data;
  },

  reviewDraft: async (
    enquiryId: number,
    draftId: number,
    review: {
      status: 'approved' | 'rejected' | 'edited_and_approved';
      edited_draft_body?: string;
      reviewed_by: string;
      review_feedback?: string;
    }
  ): Promise<ResponseDraft> => {
    const res = await apiClient.post<ResponseDraft>(
      `/enquiries/${enquiryId}/drafts/${draftId}/review`,
      review
    );
    return res.data;
  },

  // Knowledge Base & RAG
  getDocuments: async (): Promise<DocumentItem[]> => {
    const res = await apiClient.get<DocumentItem[]>('/documents');
    return res.data;
  },

  getDocument: async (id: number): Promise<DocumentDetail> => {
    const res = await apiClient.get<DocumentDetail>(`/documents/${id}`);
    return res.data;
  },

  uploadDocument: async (file: File, title?: string): Promise<DocumentDetail> => {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);

    const res = await apiClient.post<DocumentDetail>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  deleteDocument: async (id: number): Promise<void> => {
    await apiClient.delete(`/documents/${id}`);
  },

  searchKnowledge: async (query: string, top_k = 4): Promise<SearchResultItem[]> => {
    const res = await apiClient.post<SearchResultItem[]>('/documents/search', {
      query,
      top_k,
    });
    return res.data;
  },

  // Orders
  getOrders: async (status?: string): Promise<Order[]> => {
    const res = await apiClient.get<Order[]>('/orders', { params: { status } });
    return res.data;
  },

  lookupOrder: async (orderNumber: string) => {
    const res = await apiClient.post('/orders/lookup', { order_number: orderNumber });
    return res.data;
  },

  // Audit Logs
  getAuditLogs: async (enquiryId?: number, action?: string) => {
    const res = await apiClient.get('/audit', { params: { enquiry_id: enquiryId, action } });
    return res.data;
  },
};
