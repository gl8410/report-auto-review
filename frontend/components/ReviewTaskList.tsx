import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Loader, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

interface ReviewTaskListProps {
  onSelectTask: (taskId: string) => void;
  activeTaskId: string | null;
}

export const ReviewTaskList: React.FC<ReviewTaskListProps> = ({ onSelectTask, activeTaskId }) => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTasks = async () => {
    try {
      const data = await api.getReviewTasks();
      setTasks(data || []);
    } catch (error) {
      console.error("Failed to fetch tasks", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading && (!tasks || tasks.length === 0)) {
    return <div className="p-4 text-center"><Loader className="w-6 h-6 animate-spin mx-auto"/></div>;
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
        <h3 className="font-semibold text-slate-800">Review Tasks History</h3>
      </div>
      <div className="max-h-[400px] overflow-y-auto">
        {(!tasks || tasks.length === 0) ? (
          <div className="p-8 text-center text-slate-500">No review tasks found.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => onSelectTask(task.id)}
                className={`p-4 cursor-pointer hover:bg-slate-50 transition-colors ${activeTaskId === task.id ? 'bg-indigo-50 hover:bg-indigo-100' : ''}`}
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-medium text-slate-800 truncate pr-2" title={task.document_name}>
                    {task.document_name}
                  </div>
                  <div className="flex-shrink-0">
                    {task.status === 'COMPLETED' && <CheckCircle className="w-4 h-4 text-emerald-500" />}
                    {task.status === 'FAILED' && <XCircle className="w-4 h-4 text-red-500" />}
                    {(task.status === 'PROCESSING' || task.status === 'PENDING') && <Loader className="w-4 h-4 text-indigo-500 animate-spin" />}
                    {task.status === 'CANCELLED' && <AlertCircle className="w-4 h-4 text-slate-400" />}
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-slate-500">
                  <span>{new Date(task.created_at).toLocaleString()}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] ${
                    task.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-700' :
                    task.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                    task.status === 'PROCESSING' ? 'bg-indigo-100 text-indigo-700' :
                    'bg-slate-100 text-slate-700'
                  }`}>
                    {task.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};