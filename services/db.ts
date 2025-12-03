import { Rule } from '../types';

const API_URL = 'http://localhost:8000';

export const getAllRules = async (): Promise<Rule[]> => {
  try {
    const response = await fetch(`${API_URL}/rules`);
    if (!response.ok) throw new Error('Failed to fetch rules');
    return await response.json();
  } catch (error) {
    console.error("API Connection Error:", error);
    // Return empty array if backend is offline so UI doesn't crash completely
    return [];
  }
};

export const saveRule = async (rule: Rule): Promise<void> => {
  await fetch(`${API_URL}/rules`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule)
  });
};

export const saveRules = async (rules: Rule[]): Promise<void> => {
  await fetch(`${API_URL}/rules/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules)
  });
};

export const deleteRuleFromDB = async (id: string): Promise<void> => {
  await fetch(`${API_URL}/rules/${id}`, {
    method: 'DELETE'
  });
};

export const clearRulesDB = async (): Promise<void> => {
  await fetch(`${API_URL}/rules`, {
    method: 'DELETE'
  });
};
