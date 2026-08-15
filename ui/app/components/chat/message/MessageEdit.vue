<script setup lang="ts">
import type { UIMessage } from 'ai'
import { Button } from '~/components/ui/button'
import { Textarea } from '~/components/ui/textarea'

const props = defineProps<{
  message: UIMessage
  text: string
}>()

const emit = defineEmits<{
  save: [message: UIMessage, text: string]
  cancel: []
}>()

const editingText = ref(props.text)
</script>

<template>
  <div class="flex flex-col gap-2 w-full">
    <Textarea
      v-model="editingText"
      autofocus
      class="p-2 border border-input rounded-md resize-none min-h-[60px] bg-background focus-visible:ring-1"
      placeholder="Edit your message..."
      @keydown.enter.meta.prevent="emit('save', message, editingText)"
    />

    <div class="flex gap-1.5 justify-end">
      <Button
        size="sm"
        variant="outline"
        @click="emit('cancel')"
      >
        Cancel
      </Button>
      <Button
        size="sm"
        :disabled="!editingText.trim() || editingText === text"
        @click="emit('save', message, editingText)"
      >
        Save
      </Button>
    </div>
  </div>
</template>
