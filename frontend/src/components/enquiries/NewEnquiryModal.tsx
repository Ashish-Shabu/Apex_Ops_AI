import React, { useState } from 'react';
import { X, Send, Sparkles, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';

interface NewEnquiryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const NewEnquiryModal: React.FC<NewEnquiryModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [channel, setChannel] = useState('email');
  const [subject, setSubject] = useState('');
  const [orderNumber, setOrderNumber] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerName || !customerEmail || !subject || !message) {
      setError('Please fill in all required fields.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.createEnquiry({
        customer_name: customerName,
        customer_email: customerEmail,
        channel,
        subject,
        message,
        order_number: orderNumber ? orderNumber.trim() : undefined,
      });

      // Reset and close
      setCustomerName('');
      setCustomerEmail('');
      setSubject('');
      setOrderNumber('');
      setMessage('');
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to create enquiry:', err);
      setError(err?.response?.data?.detail || 'Failed to create enquiry. Check inputs.');
    } finally {
      setSubmitting(false);
    }
  };

  const fillSampleOrderEnquiry = () => {
    setCustomerName('Michael Brown');
    setCustomerEmail('michael.brown@example.com');
    setChannel('email');
    setSubject('Update on ANC Headset shipment');
    setOrderNumber('ORD-1003');
    setMessage('Hello support, I placed order ORD-1003 yesterday for the ANC Wireless Headset. When is it expected to dispatch from your warehouse?');
  };

  const fillSampleReturnEnquiry = () => {
    setCustomerName('Sarah Jenkins');
    setCustomerEmail('sarah.j@example.com');
    setChannel('web_chat');
    setSubject('Question about returning defective keyboard');
    setOrderNumber('ORD-1002');
    setMessage('Hi, the wireless mechanical keyboard I bought keeps disconnecting randomly. Can I return this for a replacement or full refund under warranty? Do you cover shipping?');
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-base font-bold text-slate-900">New Customer Enquiry</h3>
            <p className="text-xs text-slate-500">
              Submit a support ticket. AI will automatically classify, triage, and extract metadata.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Sample Buttons */}
        <div className="px-6 py-2.5 bg-indigo-50/60 border-b border-indigo-100 flex items-center justify-between text-xs">
          <span className="font-semibold text-indigo-900 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Load Realistic Sample:</span>
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={fillSampleOrderEnquiry}
              className="px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-100 font-medium text-[11px]"
            >
              Order Status (ORD-1003)
            </button>
            <button
              type="button"
              onClick={fillSampleReturnEnquiry}
              className="px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-100 font-medium text-[11px]"
            >
              Refund / Warranty
            </button>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Customer Name *
              </label>
              <input
                type="text"
                required
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="e.g. John Doe"
                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Customer Email *
              </label>
              <input
                type="email"
                required
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="john.doe@example.com"
                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Channel</label>
              <select
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                <option value="email">Email</option>
                <option value="web_chat">Web Chat</option>
                <option value="contact_form">Contact Form</option>
                <option value="phone_transcription">Phone Transcription</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Order Reference Number
              </label>
              <input
                type="text"
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                placeholder="e.g. ORD-1002"
                className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Subject Line *
            </label>
            <input
              type="text"
              required
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Where is my tracking number?"
              className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Message Content *
            </label>
            <textarea
              rows={4}
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Full customer enquiry message..."
              className="w-full p-3 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 leading-relaxed font-sans"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors shadow-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{submitting ? 'Creating & Classifying...' : 'Submit Enquiry'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
