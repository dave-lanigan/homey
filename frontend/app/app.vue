<script setup lang="ts">
const { messages, isLoading, error, sendMessage, clearMessages } = useChat()

const input = ref('')
const chatContainer = ref<HTMLElement | null>(null)

async function handleSubmit() {
  const text = input.value.trim()
  if (!text) return
  input.value = ''
  await sendMessage(text)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

watch(
  messages,
  async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  },
  { deep: true },
)
</script>

<template>
  <div class="flex flex-col h-screen bg-white">
    <!-- Header -->
    <header class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
      <div class="flex items-center gap-2">
        <span class="text-xl">🏠</span>
        <h1 class="text-lg font-semibold text-gray-900">Homey</h1>
        <span class="text-sm text-gray-500">AI Airbnb Assistant</span>
      </div>
      <button
        class="text-sm text-gray-500 hover:text-gray-700 transition-colors"
        @click="clearMessages"
      >
        New chat
      </button>
    </header>

    <!-- Messages -->
    <div
      ref="chatContainer"
      class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
    >
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
        <span class="text-5xl mb-4">🏠</span>
        <h2 class="text-2xl font-semibold text-gray-900 mb-2">Find your perfect stay</h2>
        <p class="text-gray-500 max-w-sm">
          Ask me anything about Airbnb listings. I'll help you find the ideal place based on
          location, budget, amenities, and more.
        </p>
      </div>

      <ChatMessage
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />

      <div v-if="isLoading && messages[messages.length - 1]?.content === ''" class="flex justify-start">
        <div class="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
          <span class="flex gap-1">
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </span>
        </div>
      </div>

      <div v-if="error" class="flex justify-center">
        <p class="text-sm text-red-500 bg-red-50 px-4 py-2 rounded-lg">{{ error }}</p>
      </div>
    </div>

    <!-- Input -->
    <div class="border-t border-gray-200 bg-white px-4 py-4">
      <form class="flex items-end gap-2 max-w-3xl mx-auto" @submit.prevent="handleSubmit">
        <textarea
          v-model="input"
          rows="1"
          placeholder="Message Homey..."
          class="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-shadow"
          :disabled="isLoading"
          @keydown="handleKeydown"
        />
        <button
          type="submit"
          :disabled="isLoading || !input.trim()"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </form>
      <p class="text-center text-xs text-gray-400 mt-2">
        Homey can make mistakes. Verify important information.
      </p>
    </div>
  </div>
</template>

