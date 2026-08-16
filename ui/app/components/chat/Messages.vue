<script setup lang="ts">
import type { UIMessage } from 'ai'

const props = defineProps<{
  messages: UIMessage[]
  status: 'ready' | 'streaming' | 'error'
  processingStatus: string | null
}>()

const scrollContainer = ref<HTMLDivElement | null>(null)

function scrollToBottom() {
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

function isProcessingMessage(message: UIMessage, index: number) {
  const hasText = message.parts.some(part => part.type === 'text' && part.text.trim())
  return props.status === 'streaming'
    && message.role === 'assistant'
    && index === props.messages.length - 1
    && !hasText
}

// Watch for message changes to auto-scroll
watch(() => props.messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

watch(() => props.processingStatus, () => {
  nextTick(scrollToBottom)
})

onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div ref="scrollContainer" class="flex-1 overflow-y-auto px-4 py-8 space-y-7 min-h-0 bg-background">
    <div class="max-w-3xl mx-auto w-full space-y-7">
      <div
        v-for="(msg, index) in messages"
        :key="msg.id"
        class="flex flex-col gap-2"
        :class="msg.role === 'user' ? 'items-end' : 'items-start'"
      >
        <!-- Avatar/Header -->
        <div class="flex items-center gap-2">
          <Icon
            v-if="msg.role === 'user'"
            name="i-lucide-user"
            class="h-4 w-4 text-muted-foreground"
          />
          <Logo v-else class="h-5 w-5 text-muted-foreground" />
          <span class="text-xs font-semibold text-muted-foreground">
            {{ msg.role === 'user' ? 'You' : 'Homey' }}
          </span>
        </div>

        <!-- Content Box -->
        <div
          class="max-w-full rounded-3xl p-4 text-base border border-border/60 shadow-soft"
          :class="msg.role === 'user' ? 'bg-secondary text-secondary-foreground rounded-tr-md' : 'bg-card text-foreground rounded-tl-md'"
        >
          <!-- Active Search Filters Header -->
          <div
            v-if="msg.role === 'assistant' && (msg as any).search"
            class="flex flex-col gap-2 pb-3 mb-3 border-b border-border/40 max-w-xl"
          >
            <div class="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Icon name="i-lucide-sliders-horizontal" class="h-3.5 w-3.5" />
              <span>Applied Search Criteria:</span>
            </div>

            <div class="flex flex-wrap gap-1.5">
              <Badge v-if="(msg as any).search.location" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <Icon name="i-lucide-map-pin" class="h-3 w-3 mr-1 shrink-0" />
                <span>{{ (msg as any).search.location }}</span>
              </Badge>

              <Badge v-if="(msg as any).search.checkin" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <Icon name="i-lucide-calendar" class="h-3 w-3 mr-1 shrink-0" />
                <span>{{ (msg as any).search.checkin }}</span>
                <span v-if="(msg as any).search.nights"> ({{ (msg as any).search.nights }} nights)</span>
              </Badge>

              <Badge v-if="(msg as any).search.guests" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <Icon name="i-lucide-users" class="h-3 w-3 mr-1 shrink-0" />
                <span>{{ (msg as any).search.guests }} guests</span>
              </Badge>

              <Badge v-if="(msg as any).search.room_type" variant="secondary" class="text-xs py-0.5 bg-accent/60 capitalize">
                <span>{{ (msg as any).search.room_type.replace('_', ' ') }}</span>
              </Badge>

              <Badge v-if="(msg as any).search.max_price" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>Max ${{ (msg as any).search.max_price }}</span>
              </Badge>

              <Badge v-for="a in ((msg as any).search.amenities ?? [])" :key="a" variant="secondary" class="text-xs py-0.5 bg-accent/60 capitalize">
                <span>{{ a.replace('_', ' ') }}</span>
              </Badge>

              <Badge v-for="kw in ((msg as any).search.keywords ?? [])" :key="kw" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>#{{ kw }}</span>
              </Badge>

              <Badge v-if="(msg as any).search.superhost" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>Superhost</span>
              </Badge>
              <Badge v-if="(msg as any).search.instant_book" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>Instant Book</span>
              </Badge>
              <Badge v-if="(msg as any).search.self_checkin" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>Self Check-in</span>
              </Badge>
              <Badge v-if="(msg as any).search.use_vision" variant="secondary" class="text-xs py-0.5 bg-accent/60">
                <span>Vision rerank</span>
              </Badge>
            </div>
          </div>

          <!-- Live processing state, replaced by content when text starts -->
          <div
            v-if="isProcessingMessage(msg, index)"
            class="flex items-center gap-3 min-w-52"
            role="status"
            aria-live="polite"
          >
            <ChatIndicator />
            <span class="text-sm text-muted-foreground">
              {{ processingStatus || 'Thinking' }}
            </span>
          </div>
          <slot v-else name="content" :message="msg" />
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1.5 px-1 min-h-8">
          <slot name="actions" :message="msg" />
        </div>
      </div>

    </div>
  </div>
</template>
