import React, { useState } from 'react';
import { Layout } from './components/Layout';
import { RuleManager } from './components/RuleManager';
import { DocumentUploader } from './components/DocumentUploader';
import { ReviewEngine } from './components/ReviewEngine';
import { ReportViewer } from './components/ReportViewer';
import { HistoryAnalysis } from './components/HistoryAnalysis';
import { ComparisonManager } from './components/ComparisonManager';
import { AppStep } from './types';

function App() {
  const [currentView, setCurrentView] = useState<AppStep>(AppStep.Rules);

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

export default App;