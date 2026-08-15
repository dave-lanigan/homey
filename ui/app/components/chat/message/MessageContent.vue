<script setup lang="ts">
import { isTextUIPart } from 'ai'
import type { UIMessage } from 'ai'
import { isPartStreaming } from '@nuxt/ui/utils/ai'
import type { ListingResult } from '~~/shared/utils/search'
import { Button } from '~/components/ui/button'

const props = defineProps<{
  message: UIMessage
  editing: boolean
}>()

const activeModal = useState<any>('active-modal')

const emit = defineEmits<{
  save: [message: UIMessage, text: string]
  cancelEdit: []
}>()

function openListings() {
  const listings = (props.message as UIMessage & { listings?: ListingResult[] }).listings
  if (listings?.length) {
    activeModal.value = { type: 'listings', listings }
  }
}
</script>

<template>
  <img
    v-if="(message as any).image"
    :src="(message as any).image"
    alt="Reference image"
    class="mb-3 max-h-72 max-w-full rounded-lg object-contain"
  />
  <template v-for="(part, index) in message.parts" :key="`${message.id}-${index}`">
    <template v-if="isTextUIPart(part)">
      <ChatComark
        v-if="message.role === 'assistant'"
        :value="part.text"
        :streaming="isPartStreaming(part)"
      />
      <template v-else>
        <ChatMessageEdit
          v-if="editing"
          :message="message"
          :text="part.text"
          @save="(msg, text) => emit('save', msg, text)"
          @cancel="emit('cancelEdit')"
        />
        <p v-else class="whitespace-pre-wrap">
          {{ part.text }}
        </p>
      </template>
    </template>
  </template>
  <Button
    v-if="message.role === 'assistant' && (message as any).listings?.length"
    class="mt-4 w-full sm:w-auto"
    @click="openListings"
  >
    <Icon name="i-lucide-building-2" class="mr-2 h-4 w-4" />
    View {{ (message as any).listings.length }} listings
  </Button>
</template>
