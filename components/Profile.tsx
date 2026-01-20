import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../services/supabase';

interface UserProfile {
  id: string;
  email: string;
  credits: number;
}

export const Profile: React.FC = () => {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');

  useEffect(() => {
    fetchProfile();
  }, [user]);

  const fetchProfile = async () => {
    if (!user) return;
    try {
      // We can fetch from our backend API which syncs with Supabase + credits
      // Assuming we have an endpoint GET /api/v1/users/me calling get_current_user
      // We need to inject the token.
      const { data: session } = await supabase.auth.getSession();
      const token = session.session?.access_token;

      if (!token) return;

      const res = await fetch('http://localhost:8000/api/v1/users/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } catch (error) {
      console.error("Failed to fetch profile", error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMessage('Updating...');
    try {
      const { error } = await supabase.auth.updateUser({ password: password });
      if (error) throw error;
      setPasswordMessage('Password updated successfully!');
      setPassword('');
    } catch (error: any) {
      setPasswordMessage(`Error: ${error.message}`);
    }
  };

  if (loading) return <div>Loading profile...</div>;

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded shadow">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">User Profile</h2>
        <button onClick={signOut} className="text-red-600 hover:text-red-800">Sign Out</button>
      </div>

      <div className="mb-8 p-4 bg-gray-50 rounded">
        <p><strong>Email:</strong> {user?.email}</p>
        <p className="mt-2"><strong>Credits:</strong> <span className="font-bold text-green-600 text-lg">{profile?.credits ?? 0}</span></p>
      </div>

      <div className="border-t pt-6">
        <h3 className="text-xl font-semibold mb-4">Change Password</h3>
        <form onSubmit={handleUpdatePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">New Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 mt-1 border rounded"
              minLength={6}
              required
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Update Password
          </button>
          {passwordMessage && <p className="text-sm mt-2 text-gray-600">{passwordMessage}</p>}
        </form>
      </div>
    </div>
  );
};