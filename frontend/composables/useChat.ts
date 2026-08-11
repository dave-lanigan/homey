export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export function useChat() {
  const config = useRuntimeConfig()
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function sendMessage(content: string) {
    if (!content.trim() || isLoading.value) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: content.trim(),
    }
    messages.value.push(userMessage)

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
    }
    messages.value.push(assistantMessage)
    isLoading.value = true
    error.value = null

    try {
      const response = await fetch(`${config.public.apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.value
            .filter((m) => m.id !== assistantMessage.id)
            .map(({ role, content }) => ({ role, content })),
        }),
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        assistantMessage.content += decoder.decode(value, { stream: true })
        // Trigger reactivity
        messages.value = [...messages.value]
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'An error occurred'
      messages.value = messages.value.filter((m) => m.id !== assistantMessage.id)
    } finally {
      isLoading.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    error.value = null
  }

  return { messages, isLoading, error, sendMessage, clearMessages }
}
