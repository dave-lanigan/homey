<script setup lang="ts">
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu'
import { Button } from '~/components/ui/button'

const props = defineProps<{
  chatId: string
  title?: string | null
}>()

const emit = defineEmits<{
  'update:title': [title: string]
}>()

const { renameChat, deleteChat } = useChatActions()

const displayTitle = computed(() => props.title || 'Untitled')

async function handleRename() {
  const newTitle = await renameChat(props.chatId, props.title)
  if (newTitle) emit('update:title', newTitle)
}

async function handleDelete() {
  await deleteChat(props.chatId)
}
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button
        variant="ghost"
        class="font-semibold text-base flex items-center gap-1.5 h-9 px-3 rounded-md hover:bg-accent group max-w-[200px] focus-visible:ring-0 focus-visible:ring-offset-0"
        :class="{ 'text-muted-foreground': !title }"
      >
        <span class="truncate">{{ displayTitle }}</span>
        <Icon name="i-lucide-chevron-down" class="h-4 w-4 text-muted-foreground shrink-0 group-data-[state=open]:rotate-180 transition-transform duration-200" />
      </Button>
    </DropdownMenuTrigger>

    <DropdownMenuContent align="start" class="w-44">
      <DropdownMenuItem @click="handleRename">
        <Icon name="i-lucide-pencil" class="h-4 w-4 mr-2" />
        <span>Rename</span>
      </DropdownMenuItem>
      <DropdownMenuItem class="text-destructive focus:text-destructive" @click="handleDelete">
        <Icon name="i-lucide-trash" class="h-4 w-4 mr-2" />
        <span>Delete</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
