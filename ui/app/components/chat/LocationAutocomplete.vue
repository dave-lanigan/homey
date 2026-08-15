<script setup lang="ts">
import { Input } from '~/components/ui/input'
import { Card } from '~/components/ui/card'

const model = defineModel<string>({ default: '' })

const cities = ref<string[]>([])
const loaded = ref(false)
const focused = ref(false)

async function loadCities() {
  if (loaded.value) return
  loaded.value = true
  try {
    cities.value = await $fetch<string[]>('/cities.json')
  } catch {
    loaded.value = false
  }
}

const suggestions = computed(() => {
  const q = (model.value ?? '').trim().toLowerCase()
  if (!q || !cities.value.length) return []
  const out: string[] = []
  for (const city of cities.value) {
    if (city.toLowerCase().includes(q)) {
      out.push(city)
      if (out.length >= 10) break
    }
  }
  return out
})

const showDropdown = computed(() => focused.value && suggestions.value.length > 0)

function selectCity(city: string) {
  model.value = city
  focused.value = false
}

let blurTimeout: ReturnType<typeof setTimeout> | undefined
function onBlur() {
  // Delay blur to allow click on item
  blurTimeout = setTimeout(() => {
    focused.value = false
  }, 200)
}

function onFocus() {
  clearTimeout(blurTimeout)
  focused.value = true
  loadCities()
}
</script>

<template>
  <div class="relative w-full">
    <div class="relative flex items-center">
      <Icon name="i-lucide-map-pin" class="absolute left-2.5 h-4 w-4 text-muted-foreground shrink-0" />
      <Input
        v-model="model"
        type="text"
        placeholder="City, Country"
        class="pl-9 h-9 w-full bg-background"
        @focus="onFocus"
        @blur="onBlur"
      />
    </div>

    <Card
      v-if="showDropdown"
      class="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-y-auto shadow-md border border-border bg-popover text-popover-foreground rounded-md py-1"
    >
      <button
        v-for="city in suggestions"
        :key="city"
        type="button"
        class="w-full text-left px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground transition-colors truncate"
        @click="selectCity(city)"
      >
        {{ city }}
      </button>
    </Card>
  </div>
</template>
