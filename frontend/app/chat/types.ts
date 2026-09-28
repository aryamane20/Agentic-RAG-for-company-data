export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sourceDocuments?: string[];
  isDenial?: boolean;
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
}
