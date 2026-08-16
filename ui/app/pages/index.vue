<script setup lang="ts">
import { Button } from '~/components/ui/button'

const input = ref('')
const loading = ref(false)
const chatId = crypto.randomUUID()
const search = useState<SearchParams>('chat-search', () => ({ room_type: 'apartment', guests: 2, amenities: [], keywords: [] }))
const attachedImage = useState<string | null>('chat-attached-image', () => null)
const searchForm = ref<{ close: () => void } | null>(null)

const { createChat } = useChats()

const greeting = "Hey, there."

async function createNewChat(prompt: string, image?: string | null) {
  input.value = prompt
  loading.value = true

  createChat(chatId, prompt, image)
  attachedImage.value = null
  navigateTo(`/chat/${chatId}`)
}

function onSubmit() {
  const text = input.value.trim()
    || (attachedImage.value ? 'Find listings similar to this image' : '')
    || (search.value.location ? 'Updating Airbnb Filters' : '')
  if (text || attachedImage.value) {
    searchForm.value?.close()
    createNewChat(text, attachedImage.value)
  }
}

const quickChats = [
  {
    label: 'Find me a studio in Paris',
    icon: 'i-lucide-house'
  },
  {
    label: 'Best neighborhoods in Lisbon?',
    icon: 'i-lucide-map'
  },
  {
    label: 'Help me plan a beach getaway',
    icon: 'i-lucide-sun'
  },
  {
    label: 'What is the weather in Barcelona?',
    icon: 'i-lucide-cloud-sun'
  },
  {
    label: 'Find a pet-friendly stay near me',
    icon: 'i-lucide-paw-print'
  },
  {
    label: 'Budget tips for a trip to Tokyo',
    icon: 'i-lucide-ticket'
  }
]
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0 relative">
    <Navbar />

    <div class="flex-1 flex flex-col justify-center items-center overflow-y-auto px-4 py-20 bg-background/50">
      <div class="max-w-3xl w-full flex flex-col gap-7 sm:gap-9">
        <div class="space-y-2">
          <p class="text-xs font-bold uppercase tracking-[0.22em] text-primary">Find a place to feel at home</p>
          <h1 class="text-3xl sm:text-5xl text-foreground font-extrabold tracking-tight">
          {{ greeting }}
          </h1>
        </div>

        <!-- Custom Chat Prompt -->
        <ChatPrompt
          v-model="input"
          v-model:image="attachedImage"
          :disabled="loading"
          :has-search="!!search.location"
          @submit="onSubmit"
        />

        <!-- Search Form for Pre-configuring search parameters -->
        <ChatSearchForm ref="searchForm" v-model="search" />

        <div class="flex flex-wrap gap-2">
          <Button
            v-for="quickChat in quickChats"
            :key="quickChat.label"
            size="sm"
            variant="outline"
            class="rounded-full text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            @click="createNewChat(quickChat.label)"
          >
            <Icon :name="quickChat.icon" class="mr-1.5 h-3.5 w-3.5 text-muted-foreground/80 shrink-0" />
            <span>{{ quickChat.label }}</span>
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
