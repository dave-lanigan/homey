<script setup lang="ts">
import { Button } from '~/components/ui/button'

const activeModal = useState<any>('active-modal')

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

function confirm() {
  const resolve = activeModal.value.resolve
  activeModal.value = { type: null }
  if (resolve) resolve(true)
}
</script>

<template>
  <Dialog :open="true" @update:open="handleClose">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Delete chat</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete this chat? This cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <DialogFooter class="flex flex-row-reverse gap-2 justify-start">
        <Button variant="destructive" @click="confirm">
          Delete
        </Button>
        <Button variant="ghost" @click="cancel">
          Cancel
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
