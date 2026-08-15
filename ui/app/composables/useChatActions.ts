import { toast } from 'vue-sonner'

export interface ActiveModalState {
  type: 'rename' | 'delete' | null
  chatId?: string
  currentTitle?: string
  resolve?: (value: any) => void
}

export function useChatActions() {
  const route = useRoute()
  const { renameChat: renameChatInStore, deleteChat: deleteChatInStore } = useChats()

  const activeModal = useState<ActiveModalState>('active-modal', () => ({ type: null }))

  function renameChat(id: string, currentTitle?: string | null): Promise<string | null> {
    return new Promise((resolve) => {
      activeModal.value = {
        type: 'rename',
        chatId: id,
        currentTitle: currentTitle ?? '',
        resolve: (val) => {
          if (val && val !== currentTitle) {
            renameChatInStore(id, val)
            resolve(val)
          } else {
            resolve(null)
          }
        }
      }
    })
  }

  function deleteChat(id: string): Promise<boolean> {
    return new Promise((resolve) => {
      activeModal.value = {
        type: 'delete',
        chatId: id,
        resolve: (confirmed) => {
          if (confirmed) {
            deleteChatInStore(id)
            toast('Chat deleted', {
              description: 'Your chat has been deleted',
            })
            if (route.params.id === id) {
              navigateTo('/')
            }
            resolve(true)
          } else {
            resolve(false)
          }
        }
      }
    })
  }

  return {
    renameChat,
    deleteChat
  }
}
