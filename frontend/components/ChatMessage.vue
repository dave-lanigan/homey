<script setup lang="ts">
import type { Message } from '~/composables/useChat'

defineProps<{ message: Message }>()
</script>

<template>
  <div
    class="flex w-full"
    :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
      :class="
        message.role === 'user'
          ? 'bg-gray-900 text-white rounded-br-sm'
          : 'bg-gray-100 text-gray-900 rounded-bl-sm'
      "
    >
      <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>
    </div>
  </div>
</template>
