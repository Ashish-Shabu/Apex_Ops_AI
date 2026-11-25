import React, { useState, useEffect } from 'react';
import { 
  Package, 
  Search, 
  Truck, 
  CheckCircle2, 
  Clock, 
  RotateCcw, 
  ShieldCheck,
  Wrench,
  AlertCircle
} from 'lucide-react';
import { Order } from '../../types';
import { api } from '../../services/api';

export const OrdersView: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterStatus, setFilterStatus] = useState<string>('all');

  // Tool tester states
  const [searchOrderNumber, setSearchOrderNumber] = useState<string>('ORD-1002');
  const [lookupResult, setLookupResult] = useState<any>(null);
  const [lookupLoading, setLookupLoading] = useState<boolean>(false);
  const [lookupExecuted, setLookupExecuted] = useState<boolean>(false);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const data = await api.getOrders(filterStatus !== 'all' ? filterStatus : undefined);
      setOrders(data);
    } catch (err) {
      console.error('Failed to load orders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [filterStatus]);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchOrderNumber.trim()) return;

    setLookupLoading(true);
    try {
      const res = await api.lookupOrder(searchOrderNumber.trim());
      setLookupResult(res);
      setLookupExecuted(true);
    } catch (err) {
      console.error('Order lookup failed:', err);
    } finally {
      setLookupLoading(false);
    }
  };

  const getOrderStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'delivered':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            <span>Delivered</span>
          </span>
        );
      case 'in_transit':
      case 'shipped':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
            <Truck className="w-3 h-3 text-blue-500" />
            <span>In Transit</span>
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            <span>Processing</span>
          </span>
        );
      case 'refunded':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200">
            <RotateCcw className="w-3 h-3 text-purple-500" />
            <span>Refunded</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700">
            <span>{status}</span>
          </span>
        );
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Tool Calling Inspector Workbench (Requirement 3.E) */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-2xl p-6 shadow-md border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-6 h-6 rounded bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                <Wrench className="w-3.5 h-3.5" />
              </span>
              <h3 className="text-base font-bold text-white">Controlled Backend Tool Inspector</h3>
            </div>
            <p className="text-xs text-slate-300">
              Tool function <code className="text-indigo-300 font-mono">lookup_order(order_number)</code> executed by the LLM during draft generation.
              Guarantees zero arbitrary SQL execution through strict ORM parameterization.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs bg-indigo-900/50 border border-indigo-500/30 px-3 py-1.5 rounded-lg text-indigo-200">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>SQL Injection Safe</span>
          </div>
        </div>

        <form onSubmit={handleLookup} className="flex flex-wrap gap-2 mb-4">
          <input
            type="text"
            value={searchOrderNumber}
            onChange={(e) => setSearchOrderNumber(e.target.value)}
            placeholder="Enter Order # (e.g. ORD-1001, ORD-1002)..."
            className="flex-1 min-w-[220px] px-3.5 py-2 text-xs bg-slate-800/90 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
          />
          <button
            type="submit"
            disabled={lookupLoading}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            <Search className={`w-3.5 h-3.5 ${lookupLoading ? 'animate-spin' : ''}`} />
            <span>{lookupLoading ? 'Invoking Tool...' : 'Execute Tool Call'}</span>
          </button>
        </form>

        {/* Quick Sample Order Pills */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>Sample Orders:</span>
          {['ORD-1001', 'ORD-1002', 'ORD-1003', 'ORD-1004', 'ORD-9999'].map((num) => (
            <button
              key={num}
              type="button"
              onClick={() => setSearchOrderNumber(num)}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-indigo-300 text-[11px] font-mono border border-slate-700/80"
            >
              {num}
            </button>
          ))}
        </div>

        {/* Tool Output Result Card */}
        {lookupExecuted && (
          <div className="mt-4 p-4 bg-slate-950/80 rounded-xl border border-slate-800 text-xs font-mono">
            <div className="flex items-center justify-between text-slate-400 border-b border-slate-800 pb-2 mb-2">
              <span>TOOL RESPONSE PAYLOAD</span>
              <span className={lookupResult?.found ? 'text-emerald-400' : 'text-amber-400'}>
                {lookupResult?.found ? 'STATUS: FOUND' : 'STATUS: NOT FOUND'}
              </span>
            </div>
            <pre className="text-indigo-200 overflow-x-auto text-[11px] leading-relaxed">
              {JSON.stringify(lookupResult, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Orders Directory Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Sample Customer Orders</h3>
            <p className="text-xs text-slate-500">
              Mock business order repository queried by the operations assistant
            </p>
          </div>

          <div className="flex items-center gap-1 text-[11px]">
            {['all', 'delivered', 'in_transit', 'processing', 'refunded'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`px-2.5 py-1 rounded-md font-medium whitespace-nowrap transition-colors ${
                  filterStatus === st
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {st.replace(/_/g, ' ').toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-center text-xs text-slate-400">Loading orders...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px] border-y border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Order Number</th>
                  <th className="py-2.5 px-3">Customer</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Carrier & Tracking</th>
                  <th className="py-2.5 px-3">Total Amount</th>
                  <th className="py-2.5 px-3">Purchased Items</th>
                  <th className="py-2.5 px-3">Order Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/80">
                    <td className="py-3 px-3 font-mono font-bold text-indigo-700">
                      {o.order_number}
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900">{o.customer_name}</div>
                      <div className="text-[11px] text-slate-400">{o.customer_email}</div>
                    </td>
                    <td className="py-3 px-3">{getOrderStatusBadge(o.status)}</td>
                    <td className="py-3 px-3 text-slate-600">
                      {o.carrier ? (
                        <div>
                          <span className="font-medium">{o.carrier}</span>
                          <span className="text-[11px] font-mono text-slate-400 block">
                            {o.tracking_number || 'N/A'}
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">None assigned</span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono font-semibold text-slate-900">
                      ${o.total_amount.toFixed(2)} {o.currency}
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      {o.items?.map((it, i) => (
                        <div key={i} className="text-[11px]">
                          {it.quantity}x {it.product_name}
                        </div>
                      ))}
                    </td>
                    <td className="py-3 px-3 text-slate-500 font-mono">
                      {new Date(o.order_date).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
