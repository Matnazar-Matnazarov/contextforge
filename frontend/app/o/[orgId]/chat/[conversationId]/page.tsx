"use client";

import { useParams } from "next/navigation";
import { ChatView } from "@/components/chat-view";

export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  return <ChatView key={conversationId} conversationId={conversationId} />;
}
