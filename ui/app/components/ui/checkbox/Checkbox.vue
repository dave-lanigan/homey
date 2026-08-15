<script setup lang="ts">
import type { CheckboxRootEmits, CheckboxRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { Check } from "lucide-vue-next"
import { CheckboxIndicator, CheckboxRoot } from "reka-ui"
import { cn } from "~/lib/utils"

const props = defineProps<{
  checked?: boolean | 'indeterminate'
  disabled?: boolean
  required?: boolean
  name?: string
  value?: string
  id?: string
  class?: HTMLAttributes["class"]
}>()

defineEmits<{
  'update:checked': [value: boolean | 'indeterminate']
}>()
</script>

<template>
  <CheckboxRoot
    :checked="props.checked"
    :disabled="props.disabled"
    :required="props.required"
    :name="props.name"
    :value="props.value"
    :id="props.id"
    @update:checked="(val) => $emit('update:checked', val)"
    :class="
      cn('grid place-content-center peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
         props.class)"
  >
    <CheckboxIndicator class="grid place-content-center text-current">
      <slot>
        <Check class="h-4 w-4" />
      </slot>
    </CheckboxIndicator>
  </CheckboxRoot>
</template>
