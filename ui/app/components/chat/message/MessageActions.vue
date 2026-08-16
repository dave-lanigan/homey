<script setup lang="ts">
import type { UIMessage } from 'ai'
import { useClipboard } from '@vueuse/core'
import { getTextFromMessage } from '~/composables/useChats'
import { Button } from '~/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '~/components/ui/tooltip'

const props = defineProps<{
  message: UIMessage & { createdAt?: string | Date }
  streaming: boolean
  editing: boolean
  vote: boolean | null
}>()

const formattedDate = computed(() => {
  if (!props.message.createdAt) return null

  const date = new Date(props.message.createdAt)

  return {
    time: date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }),
    full: date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }),
    iso: date.toISOString()
  }
})

const emit = defineEmits<{
  edit: [message: UIMessage]
  regenerate: [message: UIMessage]
  vote: [message: UIMessage, isUpvoted: boolean]
}>()

const clipboard = useClipboard()

const copied = ref(false)

function copy() {
  clipboard.copy(getTextFromMessage(props.message))

  copied.value = true

  setTimeout(() => {
    copied.value = false
  }, 2000)
}
</script>

<template>
  <template v-if="message.role === 'assistant' && !streaming">
    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8"
          :class="copied ? 'text-primary' : 'text-muted-foreground'"
          aria-label="Copy response"
          @click="copy"
        >
          <Icon :name="copied ? 'i-lucide-copy-check' : 'i-lucide-copy'" class="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        Copy response
      </TooltipContent>
    </Tooltip>

    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8"
          :class="vote === true ? 'text-positive' : 'text-muted-foreground'"
          aria-label="Good response"
          @click="emit('vote', message, true)"
        >
          <Icon name="i-lucide-thumbs-up" class="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        Good response
      </TooltipContent>
    </Tooltip>

    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8"
          :class="vote === false ? 'text-negative' : 'text-muted-foreground'"
          aria-label="Bad response"
          @click="emit('vote', message, false)"
        >
          <Icon name="i-lucide-thumbs-down" class="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        Bad response
      </TooltipContent>
    </Tooltip>

    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8 text-muted-foreground"
          aria-label="Regenerate response"
          @click="emit('regenerate', message)"
        >
          <Icon name="i-lucide-rotate-cw" class="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        Regenerate response
      </TooltipContent>
    </Tooltip>
  </template>

  <template v-if="message.role === 'user' && !streaming && !editing">
    <Tooltip v-if="formattedDate">
      <TooltipTrigger as-child>
        <time :datetime="formattedDate.iso" class="text-xs text-muted-foreground mr-1.5 cursor-help">
          {{ formattedDate.time }}
        </time>
      </TooltipTrigger>
      <TooltipContent>
        {{ formattedDate.full }}
      </TooltipContent>
    </Tooltip>

    <Tooltip>
      <TooltipTrigger as-child>
        <Button
          size="icon"
          variant="ghost"
          class="h-8 w-8 text-muted-foreground"
          aria-label="Edit message"
          @click="emit('edit', message)"
        >
          <Icon name="i-lucide-pencil" class="h-4 w-4" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        Edit message
      </TooltipContent>
    </Tooltip>
  </template>
</template>
