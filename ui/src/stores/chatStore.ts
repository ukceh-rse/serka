import { create } from 'zustand'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: boolean
}

interface ChatState {
  messages: ChatMessage[]
  loading: boolean
  threadId: string
  addMessage: (msg: ChatMessage) => void
  appendToLast: (delta: string) => void
  setLoading: (v: boolean) => void
  setLastThinking: (v: boolean) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  loading: false,
  threadId: crypto.randomUUID(),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLast: (delta) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length > 0) msgs[msgs.length - 1].content += delta
      return { messages: msgs }
    }),
  setLoading: (v) => set({ loading: v }),
  setLastThinking: (v) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length > 0) msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], thinking: v }
      return { messages: msgs }
    }),
  clearMessages: () => set({ messages: [], threadId: crypto.randomUUID() }),
}))
