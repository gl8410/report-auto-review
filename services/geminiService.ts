import { GoogleGenAI, Type } from "@google/genai";
import { Rule, ReviewResult, UploadedFile, ImportanceLevel, ReviewStatus } from '../types';

// Helper to get AI instance
const getAI = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error("API Key not found. Please check your environment configuration.");
  }
  return new GoogleGenAI({ apiKey });
};

/**
 * Parses raw text content into structured rules using Gemini Flash.
 */
export const parseRulesFromContent = async (content: string): Promise<Rule[]> => {
  const ai = getAI();
  
  // Using 2.5-Flash for speed and efficiency in extraction tasks
  const modelId = 'gemini-2.5-flash';

  const prompt = `
    You are an expert engineering document parser. 
    Analyze the following text which contains a list of engineering standards or rules.
    Extract them into individual rules. 
    
    If the text implies an importance level, assign it (High, Medium, Low). 
    If not specified, infer based on keywords (e.g., "shall", "must" = High; "should" = Medium; "may" = Low).
    
    Text content:
    ${content.substring(0, 30000)} // Truncate if purely text to avoid token limits in prompt, though flash handles large context.
  `;

  try {
    const response = await ai.models.generateContent({
      model: modelId,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              id: { type: Type.STRING },
              clause: { type: Type.STRING },
              standardName: { type: Type.STRING },
              content: { type: Type.STRING },
              importance: { type: Type.STRING, enum: [ImportanceLevel.High, ImportanceLevel.Medium, ImportanceLevel.Low] }
            },
            required: ["id", "clause", "standardName", "content", "importance"]
          }
        }
      }
    });

    if (response.text) {
      return JSON.parse(response.text) as Rule[];
    }
    return [];
  } catch (error) {
    console.error("Error parsing rules:", error);
    throw error;
  }
};

/**
 * Reviews a document against a set of rules using Gemini Pro (Long Context).
 */
export const reviewDocument = async (
  file: UploadedFile, 
  rules: Rule[]
): Promise<ReviewResult[]> => {
  const ai = getAI();

  // Using 3-pro-preview for maximum context window and reasoning capability
  // to handle entire engineering reports and complex rule logic.
  const modelId = 'gemini-3-pro-preview';

  const rulesJson = JSON.stringify(rules);

  const prompt = `
    You are a strict Engineering Auditor.
    
    Your Task:
    1. Read the provided document thoroughly.
    2. Evaluate compliance against EACH of the following Rules.
    3. For each rule, determine if the document Passes, Fails, or if the rule is Not Applicable (N/A).
    4. Provide specific EVIDENCE (direct quotes) from the document.
    5. Provide REASONING for your decision.

    Rules to Check:
    ${rulesJson}

    Output Format:
    Return a JSON array where each object corresponds to a rule check.
  `;

  try {
    const response = await ai.models.generateContent({
      model: modelId,
      contents: {
        parts: [
          {
            inlineData: {
              mimeType: file.type,
              data: file.data
            }
          },
          {
            text: prompt
          }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              ruleId: { type: Type.STRING, description: "Must match the ID from the input rules" },
              status: { type: Type.STRING, enum: [ReviewStatus.Pass, ReviewStatus.Fail, ReviewStatus.NotApplicable] },
              evidence: { type: Type.STRING, description: "Quote from document or 'None' if N/A" },
              reasoning: { type: Type.STRING, description: "Explanation of findings" }
            },
            required: ["ruleId", "status", "evidence", "reasoning"]
          }
        }
      }
    });

    if (response.text) {
      return JSON.parse(response.text) as ReviewResult[];
    }
    return [];

  } catch (error) {
    console.error("Error reviewing document:", error);
    throw error;
  }
};