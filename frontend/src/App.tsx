import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { DashboardView } from './components/dashboard/DashboardView';
import { EnquiriesView } from './components/enquiries/EnquiriesView';
import { KnowledgeBaseView } from './components/knowledge/KnowledgeBaseView';
import { OrdersView } from './components/orders/OrdersView';
import { AuditView } from './components/audit/AuditView';
import { NewEnquiryModal } from './components/enquiries/NewEnquiryModal';
import { DashboardStats, HealthStatus } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const fetchStats = async () => {
    try {
      const data = await api.getDashboardStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load dashboard stats:', err);
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchHealth = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch (err) {
      console.error('Health check failed:', err);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchHealth();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100 antialiased">
      {/* Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        pendingCount={stats?.pending_enquiries || 0}
        awaitingCount={stats?.awaiting_approval_enquiries || 0}
      />

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <Header
          currentTab={currentTab}
          health={health}
          onNewEnquiry={() => setIsModalOpen(true)}
        />

        <main className="flex-1 overflow-y-auto flex flex-col">
          {currentTab === 'dashboard' && (
            <DashboardView
              stats={stats}
              loading={loadingStats}
              onNavigate={(tab) => setCurrentTab(tab)}
              onNewEnquiry={() => setIsModalOpen(true)}
            />
          )}

          {currentTab === 'enquiries' && (
            <EnquiriesView
              onRefreshStats={fetchStats}
              onNavigateOrder={(ord) => setCurrentTab('orders')}
            />
          )}

          {currentTab === 'knowledge' && (
            <KnowledgeBaseView onRefreshStats={fetchStats} />
          )}

          {currentTab === 'orders' && <OrdersView />}

          {currentTab === 'audit' && <AuditView />}
        </main>
      </div>

      {/* Modal for creating new customer enquiries */}
      <NewEnquiryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          fetchStats();
          setCurrentTab('enquiries');
        }}
      />
    </div>
  );
};

export default App;
