<script setup lang="ts">
import { Button } from '~/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { Input } from '~/components/ui/input'

const route = useRoute()
const { groups } = useChats()
const { renameChat, deleteChat } = useChatActions()

const activeModal = useState<any>('active-modal', () => ({ type: null }))

const desktopSidebarOpen = ref(true)
const desktopSidebarTrigger = ref<{ $el: HTMLElement } | null>(null)
const desktopSidebarClose = ref<{ $el: HTMLElement } | null>(null)

async function setDesktopSidebarOpen(open: boolean) {
  desktopSidebarOpen.value = open
  await nextTick()
  const target = open ? desktopSidebarClose.value : desktopSidebarTrigger.value
  target?.$el.focus()
}

// Mobile sidebar open state
const sidebarOpen = ref(false)

// Search dialog state
const searchOpen = ref(false)
const searchQuery = ref('')

const allChats = computed(() => {
  return groups.value?.flatMap(g => g.items) ?? []
})

const filteredChats = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return allChats.value
  return allChats.value.filter(c => c.label.toLowerCase().includes(q))
})

function handleSearchSelect(id: string) {
  searchOpen.value = false
  searchQuery.value = ''
  navigateTo(`/chat/${id}`)
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'o') {
    e.preventDefault()
    navigateTo('/')
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    searchOpen.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="h-screen w-screen flex bg-background text-foreground overflow-hidden">
    <!-- Desktop Sidebar -->
    <aside
      class="hidden h-full shrink-0 overflow-hidden bg-sidebar transition-[width,border-color] duration-500 ease-in-out motion-reduce:transition-none lg:block"
      :class="desktopSidebarOpen ? 'w-64 border-r border-sidebar-border/70' : 'w-0 border-r-0 border-transparent'"
      :inert="!desktopSidebarOpen"
    >
      <div
        class="flex h-full min-h-0 w-64 flex-col gap-6 p-5 transition-[transform,opacity] duration-500 ease-in-out motion-reduce:transition-none select-none"
        :style="{
          transform: desktopSidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
          opacity: desktopSidebarOpen ? '1' : '0',
        }"
      >
        <!-- Logo Header -->
        <div class="flex items-center justify-between">
          <NuxtLink to="/" class="flex items-center gap-2 px-2">
            <Logo class="h-6 w-6 shrink-0 text-foreground" />
            <span class="text-xl font-bold tracking-tight text-foreground">Homey<span class="text-primary">.</span></span>
          </NuxtLink>
          <Button
            ref="desktopSidebarClose"
            variant="ghost"
            size="icon"
            class="h-8 w-8 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
            aria-label="Hide chat history"
            title="Hide chat history"
            @click="setDesktopSidebarOpen(false)"
          >
            <Icon name="i-lucide-panel-left-close" class="h-4 w-4" />
          </Button>
        </div>

        <!-- Main Navigation Links -->
        <nav class="space-y-1">
          <Button
            variant="ghost"
            as-child
            class="w-full justify-start h-10 px-3 hover:bg-sidebar-accent"
          >
            <NuxtLink to="/">
              <Icon name="i-lucide-circle-plus" class="mr-2 h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium">New chat</span>
              <kbd class="ml-auto pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border/60 bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
                <span class="text-xs">⌘</span>O
              </kbd>
            </NuxtLink>
          </Button>

          <Button
            variant="ghost"
            class="w-full justify-start h-10 px-3 hover:bg-sidebar-accent text-muted-foreground hover:text-foreground"
            @click="searchOpen = true"
          >
            <Icon name="i-lucide-search" class="mr-2 h-4 w-4" />
            <span class="text-sm font-medium">Search</span>
            <kbd class="ml-auto pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border border-border/60 bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100">
              <span class="text-xs">⌘</span>K
            </kbd>
          </Button>
        </nav>

        <!-- Chat History Scroll Container -->
        <div class="flex-1 overflow-y-auto min-h-0 pr-1 space-y-4">
          <div v-for="group in groups" :key="group.id" class="space-y-1">
            <h3 class="text-[10px] font-bold text-muted-foreground/60 px-3 uppercase tracking-wider">
              {{ group.label }}
            </h3>
            <div class="space-y-px">
              <div
                v-for="item in group.items"
                :key="item.id"
                class="group relative flex items-center justify-between rounded-xl hover:bg-sidebar-accent/80 transition-all"
                :class="route.params.id === item.id ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' : 'text-sidebar-foreground'"
              >
                <NuxtLink :to="`/chat/${item.id}`" class="flex-1 flex items-center gap-2 px-3 py-2 text-sm truncate min-w-0 pr-10">
                  <Icon name="i-lucide-message-circle" class="h-4 w-4 shrink-0 text-muted-foreground/80 group-hover:text-foreground transition-colors" />
                  <span class="truncate">{{ item.label }}</span>
                </NuxtLink>

                <!-- Hover Chat Actions Dropdown -->
                <div class="absolute right-1.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                  <DropdownMenu>
                    <DropdownMenuTrigger as-child>
                      <Button variant="ghost" size="icon" class="h-7 w-7 text-muted-foreground rounded-md hover:bg-accent/40 hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0">
                        <Icon name="i-lucide-ellipsis" class="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" class="w-40">
                      <DropdownMenuItem @click="renameChat(item.id, item.label)">
                        <Icon name="i-lucide-pencil" class="h-4 w-4 mr-2" />
                        <span>Rename</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem class="text-destructive focus:text-destructive" @click="deleteChat(item.id)">
                        <Icon name="i-lucide-trash" class="h-4 w-4 mr-2" />
                        <span>Delete</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <Button
      ref="desktopSidebarTrigger"
      variant="ghost"
      size="icon"
      class="absolute left-4 top-2.5 z-50 hidden h-9 w-9 text-foreground transition-opacity duration-200 hover:bg-accent motion-reduce:transition-none lg:inline-flex"
      :class="desktopSidebarOpen ? 'pointer-events-none opacity-0' : 'opacity-100'"
      :aria-hidden="desktopSidebarOpen"
      :tabindex="desktopSidebarOpen ? -1 : 0"
      aria-label="Show chat history"
      title="Show chat history"
      @click="setDesktopSidebarOpen(true)"
    >
      <Icon name="i-lucide-panel-left-open" class="h-5 w-5" />
    </Button>

    <!-- Mobile Header/Sidebar Toggle -->
    <div class="lg:hidden absolute top-2.5 left-4 z-50">
      <Sheet v-model:open="sidebarOpen">
        <SheetTrigger as-child>
          <Button variant="ghost" size="icon" class="h-9 w-9 text-foreground hover:bg-accent" aria-label="Open sidebar">
            <Icon name="i-lucide-menu" class="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" class="p-5 w-72 bg-sidebar flex flex-col justify-between h-full">
          <div class="flex flex-col gap-6 min-h-0 h-full">
            <NuxtLink to="/" class="flex items-center gap-2 px-2" @click="sidebarOpen = false">
              <Logo class="h-6 w-6 shrink-0 text-foreground" />
              <span class="text-xl font-bold tracking-tight text-foreground">Homey<span class="text-primary">.</span></span>
            </NuxtLink>

            <nav class="space-y-1">
              <Button
                variant="ghost"
                as-child
                class="w-full justify-start h-9 px-3 hover:bg-sidebar-accent"
                @click="sidebarOpen = false"
              >
                <NuxtLink to="/">
                  <Icon name="i-lucide-circle-plus" class="mr-2 h-4 w-4 text-muted-foreground" />
                  <span class="text-sm font-medium">New chat</span>
                </NuxtLink>
              </Button>
            </nav>

            <div class="flex-1 overflow-y-auto min-h-0 pr-1 space-y-4">
              <div v-for="group in groups" :key="group.id" class="space-y-1">
            <h3 class="text-[10px] font-bold text-muted-foreground/70 px-3 uppercase tracking-[0.18em]">
                  {{ group.label }}
                </h3>
                <div class="space-y-px">
                  <div
                    v-for="item in group.items"
                    :key="item.id"
                    class="group relative flex items-center justify-between rounded-xl hover:bg-sidebar-accent/80 transition-all"
                    :class="route.params.id === item.id ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium' : 'text-sidebar-foreground'"
                  >
                    <NuxtLink :to="`/chat/${item.id}`" class="flex-1 flex items-center gap-2 px-3 py-2 text-sm truncate min-w-0 pr-10" @click="sidebarOpen = false">
                      <Icon name="i-lucide-message-circle" class="h-4 w-4 shrink-0 text-muted-foreground/80" />
                      <span class="truncate">{{ item.label }}</span>
                    </NuxtLink>

                    <div class="absolute right-1.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                      <DropdownMenu>
                        <DropdownMenuTrigger as-child>
                          <Button variant="ghost" size="icon" class="h-7 w-7 text-muted-foreground rounded-md hover:bg-accent/40 hover:text-foreground">
                            <Icon name="i-lucide-ellipsis" class="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" class="w-40">
                          <DropdownMenuItem @click="renameChat(item.id, item.label)">
                            <Icon name="i-lucide-pencil" class="h-4 w-4 mr-2" />
                            <span>Rename</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem class="text-destructive focus:text-destructive" @click="deleteChat(item.id)">
                            <Icon name="i-lucide-trash" class="h-4 w-4 mr-2" />
                            <span>Delete</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>

    <!-- Main Content Container -->
    <main class="flex-1 flex flex-col h-full bg-background relative min-w-0 overflow-hidden">
      <slot />
    </main>

    <!-- Global Active Modals -->
    <ModalRename v-if="activeModal.type === 'rename'" />
    <ModalConfirm v-if="activeModal.type === 'delete'" />
    <ModalListings v-if="activeModal.type === 'listings'" />

    <!-- Command/Search Dialog -->
    <Dialog v-model:open="searchOpen">
      <DialogContent class="max-w-lg p-0 overflow-hidden bg-popover text-popover-foreground shadow-card border border-border/80 rounded-3xl">
        <DialogHeader class="p-5 border-b border-border/70">
          <DialogTitle class="text-sm font-semibold text-muted-foreground">Search chats</DialogTitle>
          <div class="mt-2 relative flex items-center">
            <Icon name="i-lucide-search" class="absolute left-3 h-4 w-4 text-muted-foreground" />
            <Input
              v-model="searchQuery"
              placeholder="Type to search..."
              class="pl-9 h-10 w-full bg-background"
              autofocus
            />
          </div>
        </DialogHeader>

        <!-- Search Results list -->
        <ScrollArea class="max-h-[300px] overflow-y-auto p-2">
          <div v-if="filteredChats.length" class="space-y-1">
            <button
              v-for="chat in filteredChats"
              :key="chat.id"
              type="button"
              class="flex items-center gap-2.5 w-full text-left px-3 py-2 rounded-md hover:bg-accent text-sm truncate"
              @click="handleSearchSelect(chat.id)"
            >
              <Icon name="i-lucide-message-circle" class="h-4 w-4 text-muted-foreground shrink-0" />
              <span class="truncate text-foreground">{{ chat.label }}</span>
            </button>
          </div>
          <div v-else class="py-12 text-center text-sm text-muted-foreground">
            No chats found matching search.
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  </div>
</template>
