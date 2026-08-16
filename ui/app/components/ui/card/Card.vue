<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "~/lib/utils"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <div
    :class="
      cn(
        'rounded-3xl border border-border/70 bg-card text-card-foreground shadow-soft',
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>
