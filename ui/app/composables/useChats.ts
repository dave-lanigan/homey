import { isToday, isYesterday, subMonths } from 'date-fns'
import type { UIMessage } from 'ai'
import type { ListingResult } from '~~/shared/utils/search'

export interface Chat {
  id: string
  title: string
  messages: UIMessage[]
  votes: Record<string, boolean | null>
  createdAt: string
  updatedAt: string
}

export interface UIChat {
  id: string
  label: string
  to: string
  icon: string
  createdAt: string
}

const STORAGE_KEY = 'homey-chats'

function loadChats(): Chat[] {
  if (!import.meta.client) return []

  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as Chat[]
  } catch {
    return []
  }
}

export function createMessage(role: 'user' | 'assistant', text: string, image?: string | null): UIMessage {
  const message = {
    id: crypto.randomUUID(),
    role,
    parts: [{ type: 'text', text }],
    createdAt: new Date().toISOString()
  } as UIMessage & { image?: string }
  if (image) message.image = image
  return message
}

export function getTextFromMessage(message: UIMessage): string {
  return message.parts
    .filter(part => part.type === 'text')
    .map(part => part.text)
    .join('')
}

export function getImageFromMessage(message: UIMessage): string | undefined {
  return (message as UIMessage & { image?: string }).image
}

export function useChats() {
  const chats = useState<Chat[]>('homey-chats', () => loadChats())

  let persistTimer: ReturnType<typeof setTimeout> | undefined
  watch(chats, () => {
    if (!import.meta.client) return

    clearTimeout(persistTimer)
    persistTimer = setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(chats.value))
    }, 200)
  }, { deep: true })

  function getChat(id: string): Chat | undefined {
    return chats.value.find(chat => chat.id === id)
  }

  function createChat(id: string, message: string, image?: string | null): Chat {
    const now = new Date().toISOString()
    const chat: Chat = {
      id,
      title: '',
      messages: [createMessage('user', message, image)],
      votes: {},
      createdAt: now,
      updatedAt: now
    }
    chats.value.unshift(chat)
    return chat
  }

  function deleteChat(id: string) {
    chats.value = chats.value.filter(chat => chat.id !== id)
  }

  function renameChat(id: string, title: string) {
    const chat = getChat(id)
    if (chat) {
      chat.title = title
      chat.updatedAt = new Date().toISOString()
    }
  }

  function addMessage(id: string, message: UIMessage) {
    const chat = getChat(id)
    if (chat) {
      chat.messages.push(message)
      chat.updatedAt = new Date().toISOString()
    }
  }

  function updateMessageContent(id: string, messageId: string, text: string) {
    const chat = getChat(id)
    if (!chat) return

    const message = chat.messages.find(m => m.id === messageId)
    if (!message) return

    const textPart = message.parts.find(part => part.type === 'text')
    if (textPart) {
      textPart.text = text
      textPart.state = 'streaming'
    }

    chat.messages = [...chat.messages]
    chat.updatedAt = new Date().toISOString()
  }

  function updateMessageListings(id: string, messageId: string, listings: ListingResult[]) {
    const chat = getChat(id)
    if (!chat) return

    const message = chat.messages.find(m => m.id === messageId)
    if (!message) return

    ;(message as UIMessage & { listings?: ListingResult[] }).listings = listings
    chat.messages = [...chat.messages]
    chat.updatedAt = new Date().toISOString()
  }

  function setMessageState(id: string, messageId: string, state: 'streaming' | 'done') {
    const chat = getChat(id)
    if (!chat) return

    const message = chat.messages.find(m => m.id === messageId)
    const textPart = message?.parts.find(part => part.type === 'text')
    if (textPart) {
      textPart.state = state
    }
  }

  function removeMessagesFrom(id: string, messageId: string) {
    const chat = getChat(id)
    if (!chat) return

    const index = chat.messages.findIndex(m => m.id === messageId)
    if (index !== -1) {
      chat.messages = chat.messages.slice(0, index)
      chat.updatedAt = new Date().toISOString()
    }
  }

  function truncateMessages(id: string, messageId: string) {
    const chat = getChat(id)
    if (!chat) return

    const index = chat.messages.findIndex(m => m.id === messageId)
    if (index !== -1) {
      chat.messages = chat.messages.slice(0, index + 1)
      chat.updatedAt = new Date().toISOString()
    }
  }

  function setVote(id: string, messageId: string, vote: boolean | null) {
    const chat = getChat(id)
    if (chat) {
      chat.votes[messageId] = vote
    }
  }

  const list = computed<UIChat[]>(() => chats.value.map(chat => ({
    id: chat.id,
    label: chat.title || 'Untitled',
    to: `/chat/${chat.id}`,
    icon: 'i-lucide-message-circle',
    createdAt: chat.createdAt
  })))

  const groups = computed(() => {
    // Group chats by date
    const today: UIChat[] = []
    const yesterday: UIChat[] = []
    const lastWeek: UIChat[] = []
    const lastMonth: UIChat[] = []
    const older: Record<string, UIChat[]> = {}

    const oneWeekAgo = subMonths(new Date(), 0.25) // ~7 days ago
    const oneMonthAgo = subMonths(new Date(), 1)

    list.value.forEach((chat) => {
      const chatDate = new Date(chat.createdAt)

      if (isToday(chatDate)) {
        today.push(chat)
      } else if (isYesterday(chatDate)) {
        yesterday.push(chat)
      } else if (chatDate >= oneWeekAgo) {
        lastWeek.push(chat)
      } else if (chatDate >= oneMonthAgo) {
        lastMonth.push(chat)
      } else {
        // Format: "January 2023", "February 2023", etc.
        const monthYear = chatDate.toLocaleDateString('en-US', {
          month: 'long',
          year: 'numeric'
        })

        if (!older[monthYear]) {
          older[monthYear] = []
        }

        older[monthYear].push(chat)
      }
    })

    // Sort older chats by month-year in descending order (newest first)
    const sortedMonthYears = Object.keys(older).sort((a, b) => {
      const dateA = new Date(a)
      const dateB = new Date(b)
      return dateB.getTime() - dateA.getTime()
    })

    // Create formatted groups for navigation
    const formattedGroups = [] as Array<{
      id: string
      label: string
      items: Array<UIChat>
    }>

    // Add groups that have chats
    if (today.length) {
      formattedGroups.push({
        id: 'today',
        label: 'Today',
        items: today
      })
    }

    if (yesterday.length) {
      formattedGroups.push({
        id: 'yesterday',
        label: 'Yesterday',
        items: yesterday
      })
    }

    if (lastWeek.length) {
      formattedGroups.push({
        id: 'last-week',
        label: 'Last week',
        items: lastWeek
      })
    }

    if (lastMonth.length) {
      formattedGroups.push({
        id: 'last-month',
        label: 'Last month',
        items: lastMonth
      })
    }

    // Add each month-year group
    sortedMonthYears.forEach((monthYear) => {
      if (older[monthYear]?.length) {
        formattedGroups.push({
          id: monthYear,
          label: monthYear,
          items: older[monthYear]
        })
      }
    })

    return formattedGroups
  })

  return {
    chats,
    list,
    groups,
    getChat,
    createChat,
    deleteChat,
    renameChat,
    addMessage,
    updateMessageContent,
    updateMessageListings,
    setMessageState,
    removeMessagesFrom,
    truncateMessages,
    setVote
  }
}
