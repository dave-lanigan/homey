<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'

const activeModal = useState<any>('active-modal')

const value = ref(activeModal.value.currentTitle ?? '')
const trimmed = computed(() => value.value.trim())

function handleClose(open: boolean) {
  if (!open) {
    cancel()
  }
}

function cancel() {
  const resolve = activeModal.value.resolve
  activeModal.value = { type: null }
  if (resolve) resolve(false)
}

function submit() {
  if (!trimmed.value) return
  const resolve = activeModal.value.resolve
  activeModal.value = { type: null }
  if (resolve) resolve(trimmed.value)
}
</script>

<template>
  <Dialog :open="true" @update:open="handleClose">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Rename chat</DialogTitle>
        <DialogDescription>Choose a new title for this chat.</DialogDescription>
      </DialogHeader>

      <div class="py-4">
        <Input
          v-model="value"
          autofocus
          placeholder="Chat title"
          class="w-full"
          @keydown.enter.prevent="submit"
        />
      </div>

      <DialogFooter class="flex flex-row-reverse gap-2 justify-start">
        <Button :disabled="!trimmed" @click="submit">
          Save
        </Button>
        <Button variant="ghost" @click="cancel">
          Cancel
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
