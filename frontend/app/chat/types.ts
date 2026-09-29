export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sourceDocuments?: string[];
  isDenial?: boolean;
  timestamp: number;
}
