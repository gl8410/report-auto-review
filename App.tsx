import React, { useState } from 'react';
import { Layout } from './components/Layout';
import { RuleManager } from './components/RuleManager';
import { DocumentUploader } from './components/DocumentUploader';
import { ReviewEngine } from './components/ReviewEngine';
import { ReportViewer } from './components/ReportViewer';
import { HistoryAnalysis } from './components/HistoryAnalysis';
import { ComparisonManager } from './components/ComparisonManager';
import { Login } from './components/Login';
import { Profile } from './components/Profile';
import { AppStep } from './types';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const AppContent = () => {
  const [currentView, setCurrentView] = useState<AppStep>(AppStep.Rules);
  const { session, loading } = useAuth();

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!session) {
    return <Login />;
  }

  const renderView = () => {
    switch (currentView) {
      case AppStep.Rules:
        return <RuleManager />;
      case AppStep.Upload:
        return <DocumentUploader />;
      case AppStep.Review:
        return <ReviewEngine onGoToReports={() => setCurrentView(AppStep.Report)} />;
      case AppStep.Report:
        return <ReportViewer />;
      case AppStep.HistoryAnalysis:
        return <HistoryAnalysis />;
      case AppStep.Comparison:
        return <ComparisonManager />;
      case AppStep.Profile:
        return <Profile />;
      default:
        return <RuleManager />;
    }
  };

  return (
    <Layout currentStep={currentView} onNavigate={setCurrentView}>
      {renderView()}
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;