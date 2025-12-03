import React, { useState } from 'react';
import { Layout } from './components/Layout';
import { RuleManager } from './components/RuleManager';
import { DocumentUploader } from './components/DocumentUploader';
import { ReviewEngine } from './components/ReviewEngine';
import { ReportViewer } from './components/ReportViewer';
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