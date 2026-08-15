<script setup lang="ts">
import type { UIMessage } from 'ai'
import { useChats, getImageFromMessage, getTextFromMessage, createMessage } from '~/composables/useChats'
import { toast } from 'vue-sonner'

const route = useRoute()
const config = useRuntimeConfig()

const { getChat, addMessage, updateMessageContent, updateMessageListings, setMessageState, removeMessagesFrom, truncateMessages, setVote, renameChat } = useChats()

const chatId = computed(() => route.params.id as string)
const chat = computed(() => getChat(chatId.value))
const messages = computed(() => chat.value?.messages ?? [])

const input = ref('')
const search = useState<SearchParams>('chat-search', () => ({ room_type: 'apartment', guests: 2, amenities: [], keywords: [] }))
const attachedImage = useState<string | null>('chat-attached-image', () => null)
const searchForm = ref<{ close: () => void } | null>(null)
const isStreaming = ref(false)
const processingStatus = ref<string | null>(null)
const error = ref<Error | null>(null)
const editingMessageId = ref<string | null>(null)

let abortController: AbortController | null = null

const status = computed(() => isStreaming.value ? 'streaming' : error.value ? 'error' : 'ready')

async function sendMessage(text?: string) {
  if (!chat.value || isStreaming.value) return

  if (text !== undefined) {
    const trimmedText = text.trim()
    const hasSearch = search.value.location?.trim()
    const submittedImage = attachedImage.value
    if (trimmedText || submittedImage || hasSearch) {
      const userMsgText = trimmedText
        || (submittedImage ? 'Find listings similar to this image' : 'Updating Airbnb Filters')
      addMessage(chat.value.id, createMessage('user', userMsgText, submittedImage))
      input.value = ''
      attachedImage.value = null
    } else {
      return
    }
  }

  const current = chat.value
  const last = current.messages[current.messages.length - 1]
  if (!last || last.role !== 'user') return

  const history = current.messages.slice(0, -1).map(m => ({ role: m.role, content: getTextFromMessage(m) }))
  const userContent = getTextFromMessage(last)
  const userImage = getImageFromMessage(last)

  const assistantMessage = createMessage('assistant', '')
  const payload = toSearchPayload(search.value)
  if (payload) {
    assistantMessage.search = JSON.parse(JSON.stringify(payload))
  }
  addMessage(current.id, assistantMessage)

  isStreaming.value = true
  processingStatus.value = 'Understanding your request'
  error.value = null
  abortController = new AbortController()

  try {
    const response = await fetch(`${config.public.apiBase}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [...history, { role: 'user', content: userContent }],
        search: toSearchPayload(search.value),
        image: userImage
      }),
      signal: abortController.signal
    })

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let content = ''
    let buffer = ''

    function handleEventLine(line: string) {
      if (!line.trim()) return
      const event = parseChatStreamEvent(line)
      if (!event) return

      if (event.type === 'status') {
        processingStatus.value = event.message
      } else if (event.type === 'text') {
        content += event.delta
        updateMessageContent(current.id, assistantMessage.id, content)
      } else if (event.type === 'search') {
        search.value = applySearchUpdate(search.value, event.data)
      } else if (event.type === 'listings') {
        updateMessageListings(current.id, assistantMessage.id, event.data)
      } else if (event.type === 'error') {
        throw new Error(event.message || 'The response could not be completed')
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        handleEventLine(line)
      }
    }
    buffer += decoder.decode()
    handleEventLine(buffer)

    setMessageState(current.id, assistantMessage.id, 'done')

    if (!current.title) {
      const firstUser = current.messages.find(m => m.role === 'user')
      if (firstUser) {
        renameChat(current.id, getTextFromMessage(firstUser).slice(0, 40).trim() || 'Untitled')
      }
    }
  } catch (e: unknown) {
    if (abortController.signal.aborted) return

    const message = e instanceof Error ? e.message : 'An error occurred'
    error.value = new Error(message)
    removeMessagesFrom(current.id, assistantMessage.id)

    toast.error(message)
  } finally {
    isStreaming.value = false
    processingStatus.value = null
    abortController = null
  }
}

function handleSubmit() {
  if (!isStreaming.value) {
    searchForm.value?.close()
    sendMessage(input.value)
  }
}

function stop() {
  abortController?.abort()
}

function startEdit(message: UIMessage) {
  if (editingMessageId.value) return
  editingMessageId.value = message.id
}

async function saveEdit(message: UIMessage, text: string) {
  if (!chat.value || !text.trim()) return

  const textPart = message.parts.find(part => part.type === 'text')
  if (textPart) textPart.text = text

  truncateMessages(chat.value.id, message.id)
  editingMessageId.value = null
  await sendMessage()
}

async function regenerateMessage(message: UIMessage) {
  if (!chat.value || message.role !== 'assistant') return

  removeMessagesFrom(chat.value.id, message.id)
  await sendMessage()
}

function getVote(messageId: string): boolean | null {
  return chat.value?.votes?.[messageId] ?? null
}

function vote(message: UIMessage, isUpvoted: boolean) {
  const current = chat.value
  if (!current) return

  const next = current.votes[message.id] === isUpvoted ? null : isUpvoted
  setVote(current.id, message.id, next)
}

onMounted(() => {
  if (chat.value && chat.value.messages.length === 1 && chat.value.messages[0].role === 'user') {
    sendMessage()
  }
})
</script>

<template>
  <div v-if="chat" class="flex-1 flex flex-col min-h-0 relative">
    <Navbar>
      <template #title>
        <ChatTitle :chat-id="chat.id" :title="chat.title" />
      </template>
    </Navbar>

    <div class="flex-1 flex flex-col min-h-0 pt-14 bg-background">
      <!-- Scrollable Message List -->
      <ChatMessages
        :messages="messages"
        :status="status"
        :processing-status="processingStatus"
      >
        <template #content="{ message }">
          <ChatMessageContent
            :message="message"
            :editing="editingMessageId === message.id"
            @save="saveEdit"
            @cancel-edit="editingMessageId = null"
          />
        </template>

        <template #actions="{ message }">
          <ChatMessageActions
            :message="message"
            :streaming="status === 'streaming' && message.id === messages[messages.length - 1]?.id"
            :editing="editingMessageId === message.id"
            :vote="getVote(message.id)"
            @vote="(_message, isUpvoted) => vote(_message, isUpvoted)"
            @edit="startEdit"
            @regenerate="regenerateMessage"
          />
        </template>
      </ChatMessages>

      <!-- Bottom Form & Input Area -->
      <div class="border-t border-border/40 p-4 bg-background/80 backdrop-blur">
        <div class="max-w-3xl mx-auto w-full space-y-3">
          <ChatPrompt
            v-model="input"
            v-model:image="attachedImage"
            :disabled="isStreaming"
            :status="status"
            :has-search="!!search.location"
            @submit="handleSubmit"
            @stop="stop"
            @reload="sendMessage"
          />

          <ChatSearchForm ref="searchForm" v-model="search" />
        </div>
      </div>
    </div>
  </div>

  <div v-else class="flex-1 flex flex-col items-center justify-center p-4 bg-background">
    <h2 class="text-xl font-bold">Chat not found</h2>
    <NuxtLink to="/" class="mt-4 text-primary hover:underline">
      Go back home
    </NuxtLink>
  </div>
</template>
