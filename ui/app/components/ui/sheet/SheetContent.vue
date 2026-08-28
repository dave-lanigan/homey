<script setup lang="ts">
import type { DialogContentEmits, DialogContentProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import type { SheetVariants } from "."
import { reactiveOmit } from "@vueuse/core"
import { X } from "lucide-vue-next"
import {
  DialogClose,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  useForwardPropsEmits,
} from "reka-ui"
import { cn } from "~/lib/utils"
import { sheetVariants } from "."

interface SheetContentProps extends DialogContentProps {
  class?: HTMLAttributes["class"]
  side?: SheetVariants["side"]
}

defineOptions({
  inheritAttrs: false,
})

const props = defineProps<SheetContentProps>()

const emits = defineEmits<DialogContentEmits>()

const delegatedProps = reactiveOmit(props, "class", "side")

const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>

<template>
  <DialogPortal>
    <DialogOverlay
      class="sheet-overlay fixed inset-0 z-50 bg-black/80"
    />
    <DialogContent
      :class="cn(sheetVariants({ side }), props.class)"
      v-bind="{ ...forwarded, ...$attrs }"
    >
      <slot />

      <DialogClose
        class="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-secondary"
      >
        <X class="w-4 h-4 text-muted-foreground" />
      </DialogClose>
    </DialogContent>
  </DialogPortal>
</template>

<style>
.sheet-overlay[data-state="open"] {
  animation: sheet-overlay-in 300ms ease-out both;
}

.sheet-overlay[data-state="closed"] {
  animation: sheet-overlay-out 250ms ease-in both;
}

.sheet-content[data-state="open"] {
  animation-duration: 400ms;
  animation-timing-function: cubic-bezier(0.22, 1, 0.36, 1);
  animation-fill-mode: both;
}

.sheet-content[data-state="closed"] {
  animation-duration: 300ms;
  animation-timing-function: cubic-bezier(0.4, 0, 1, 1);
  animation-fill-mode: both;
}

.sheet-content-left[data-state="open"] { animation-name: sheet-in-left; }
.sheet-content-left[data-state="closed"] { animation-name: sheet-out-left; }
.sheet-content-right[data-state="open"] { animation-name: sheet-in-right; }
.sheet-content-right[data-state="closed"] { animation-name: sheet-out-right; }
.sheet-content-top[data-state="open"] { animation-name: sheet-in-top; }
.sheet-content-top[data-state="closed"] { animation-name: sheet-out-top; }
.sheet-content-bottom[data-state="open"] { animation-name: sheet-in-bottom; }
.sheet-content-bottom[data-state="closed"] { animation-name: sheet-out-bottom; }

@keyframes sheet-overlay-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes sheet-overlay-out { from { opacity: 1; } to { opacity: 0; } }
@keyframes sheet-in-left { from { transform: translateX(-100%); } to { transform: translateX(0); } }
@keyframes sheet-out-left { from { transform: translateX(0); } to { transform: translateX(-100%); } }
@keyframes sheet-in-right { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes sheet-out-right { from { transform: translateX(0); } to { transform: translateX(100%); } }
@keyframes sheet-in-top { from { transform: translateY(-100%); } to { transform: translateY(0); } }
@keyframes sheet-out-top { from { transform: translateY(0); } to { transform: translateY(-100%); } }
@keyframes sheet-in-bottom { from { transform: translateY(100%); } to { transform: translateY(0); } }
@keyframes sheet-out-bottom { from { transform: translateY(0); } to { transform: translateY(100%); } }
</style>
