<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Textarea } from '~/components/ui/textarea'

const props = defineProps<{
  disabled?: boolean
  error?: Error | null
  status?: 'ready' | 'streaming' | 'error'
  hasSearch?: boolean
}>()

const emit = defineEmits<{
  submit: []
  stop: []
  reload: []
}>()

const model = defineModel<string>({ default: '' })
const image = defineModel<string | null>('image', { default: null })

const fileInput = ref<HTMLInputElement | null>(null)

function triggerFileInput() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = () => {
    image.value = reader.result as string
  }
  reader.readAsDataURL(file)

  // Clear input value so selecting same file again triggers change event
  if (fileInput.value) fileInput.value.value = ''
}

function removeImage() {
  image.value = null
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if ((model.value.trim() || image.value || props.hasSearch) && !props.disabled) {
      emit('submit')
    }
  }
}

function handleBtnClick() {
  if (props.status === 'streaming') {
    emit('stop')
  } else {
    emit('submit')
  }
}
</script>

<template>
  <div class="relative border border-border/80 rounded-3xl bg-card p-2 shadow-card transition-all focus-within:ring-2 focus-within:ring-ring/30 focus-within:border-ring/60 flex flex-col gap-2">
    <!-- Image Attachment Thumbnail Preview -->
    <div v-if="image" class="px-3 pt-2 flex flex-wrap gap-2">
      <div class="relative w-16 h-16 rounded-lg overflow-hidden border border-border group bg-background">
        <img :src="image" class="w-full h-full object-cover" alt="Attached image" />
        <Button
          type="button"
          size="icon"
          variant="destructive"
          class="absolute top-1 right-1 h-5 w-5 rounded-full shadow-md bg-destructive hover:bg-destructive/90"
          @click="removeImage"
        >
          <Icon name="i-lucide-x" class="h-3 w-3 text-white" />
        </Button>
      </div>
    </div>

    <Textarea
      v-model="model"
      :disabled="disabled"
      placeholder="Describe your ideal getaway…"
      class="w-full bg-transparent border-none shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 p-3 min-h-[80px] resize-none text-base"
      @keydown="onKeydown"
    />

    <!-- Hidden native file input -->
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      class="hidden"
      @change="onFileChange"
    />

    <div class="flex items-center justify-between border-t border-border/40 pt-2 px-1">
      <div class="flex items-center gap-1.5">
        <!-- Plus Sign Image Upload Button -->
        <Button
          type="button"
          size="icon"
          variant="ghost"
          class="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-accent rounded-lg shrink-0"
          :disabled="disabled"
          aria-label="Upload image"
          @click="triggerFileInput"
        >
          <Icon name="i-lucide-plus" class="h-4 w-4" />
        </Button>
      </div>

      <div class="flex items-center gap-2">
        <slot name="footer-right" />

        <Button
          type="button"
          size="icon"
          variant="default"
          class="h-9 w-9 rounded-full shrink-0 transition-all"
          :disabled="status !== 'streaming' && (!model.trim() && !image && !hasSearch) || disabled"
          @click="handleBtnClick"
        >
          <Icon
            :name="status === 'streaming' ? 'i-lucide-square' : 'i-lucide-arrow-up'"
            class="h-4 w-4"
          />
        </Button>
      </div>
    </div>
  </div>
</template>
