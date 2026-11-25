import React from 'react';
import { 
  LayoutDashboard, 
  Inbox, 
  BookOpen, 
  Package, 
  History, 
  Bot, 
  Sparkles,
  ShieldCheck
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  pendingCount: number;
  awaitingCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  setCurrentTab,
  pendingCount,
  awaitingCount
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { 
      id: 'enquiries', 
      label: 'Enquiry Inbox', 
      icon: Inbox,
      badge: awaitingCount > 0 ? awaitingCount : (pendingCount > 0 ? pendingCount : undefined),
      badgeColor: awaitingCount > 0 ? 'bg-amber-500 text-white' : 'bg-indigo-600 text-white'
    },
    { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
    { id: 'orders', label: 'Order Lookup', icon: Package },
    { id: 'audit', label: 'Audit Trail', icon: History },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 select-none flex-shrink-0">
      {/* Brand Logo & Name */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800 bg-slate-950/40">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
          <Bot className="w-5 h-5" />
        </div>
        <div>
          <span className="font-semibold text-white tracking-tight text-base block leading-tight">
            Apex Ops AI
          </span>
          <span className="text-[11px] text-indigo-400 font-medium tracking-wide">
            Support Platform
          </span>
        </div>
      </div>

      {/* Navigation */}
      <div className="px-3 py-4 flex-1 space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
          Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'hover:bg-slate-800/70 hover:text-white text-slate-400'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                    item.badgeColor || 'bg-slate-800 text-slate-300'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Human-in-the-Loop Safeguard Badge */}
      <div className="p-4 mx-3 mb-4 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
        <div className="flex items-center gap-2 text-indigo-400 font-medium mb-1">
          <ShieldCheck className="w-4 h-4" />
          <span>Human-in-the-Loop</span>
        </div>
        <p className="text-slate-400 text-[11px] leading-relaxed">
          AI drafts are strictly held for staff review. No auto-send without your approval.
        </p>
      </div>

      {/* User profile / session footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/20 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-slate-800 text-indigo-300 flex items-center justify-center font-semibold text-xs border border-slate-700">
          SC
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-slate-200 truncate">Staff Specialist</p>
          <p className="text-[11px] text-slate-500 truncate">clara@apexops.io</p>
        </div>
      </div>
    </aside>
  );
};
