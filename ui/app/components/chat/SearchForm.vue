<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Checkbox } from '~/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '~/components/ui/select'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '~/components/ui/popover'
import { ScrollArea } from '~/components/ui/scroll-area'
const model = defineModel<SearchParams>({ default: () => ({ amenities: [], keywords: [] }) })

const open = ref(false)

function close() {
  open.value = false
}

defineExpose({ close })

function numField(key: 'nights' | 'min_price' | 'max_price' | 'min_rating' | 'guests') {
  return computed<string>({
    get: () => (model.value[key] as number | null | undefined) == null ? '' : String(model.value[key]),
    set: (v: string) => { model.value[key] = v === '' ? null : Number(v) }
  })
}

const nights = numField('nights')
const maxPrice = numField('max_price')
const minRating = numField('min_rating')
const guests = numField('guests')

const keywordInput = ref('')

function addKeyword() {
  const val = keywordInput.value.trim()
  if (!val) return
  const current = [...(model.value.keywords ?? [])]
  if (!current.includes(val)) {
    current.push(val)
    model.value.keywords = current
  }
  keywordInput.value = ''
}

function removeKeyword(kw: string) {
  model.value.keywords = (model.value.keywords ?? []).filter(k => k !== kw)
}

const hasValues = computed(() => {
  const p = model.value
  return !!(p.location || p.checkin || p.nights != null || p.min_price != null || p.max_price != null || p.min_rating != null
    || p.guests != null || p.room_type || (p.amenities?.length) || (p.keywords?.length)
    || p.superhost || p.instant_book || p.self_checkin || p.match_all_keywords || p.use_vision)
})

function clear() {
  model.value = { amenities: [], keywords: [] }
}

function openDatePicker(event: MouseEvent) {
  const input = (event.currentTarget as HTMLElement)
    .querySelector<HTMLInputElement>('input[type="date"]')
  if (!input || input.disabled) return

  input.focus()
  if (typeof input.showPicker === 'function') {
    input.showPicker()
  } else if (event.target !== input) {
    input.click()
  }
}

// Amenities search & popover state
const amenitiesSearch = ref('')
const filteredAmenities = computed(() => {
  const q = amenitiesSearch.value.trim().toLowerCase()
  if (!q) return AMENITIES
  return AMENITIES.filter(a => a.label.toLowerCase().includes(q))
})

const selectedAmenitiesLabel = computed(() => {
  const selected = model.value.amenities ?? []
  if (!selected.length) return 'Amenities'
  const first = AMENITIES.find(a => a.value === selected[0])?.label || ''
  if (selected.length === 1) return first
  return `${first} + ${selected.length - 1} more`
})

function toggleAmenity(value: string) {
  console.log('toggleAmenity called with:', value)
  const selected = [...(model.value.amenities ?? [])]
  const idx = selected.indexOf(value)
  if (idx === -1) {
    selected.push(value)
  } else {
    selected.splice(idx, 1)
  }
  model.value.amenities = selected
  console.log('selected amenities is now:', model.value.amenities)
}
</script>

<template>
  <section class="border border-border/80 rounded-3xl bg-card/90 p-4 shadow-soft">
    <div class="flex items-center justify-between gap-2">
      <button
        class="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        type="button"
        :aria-expanded="open"
        @click="open = !open"
      >
        <Icon name="i-lucide-sliders-horizontal" class="w-4 h-4" />
        Refine your stay
        <Icon
          :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          class="w-4 h-4 transition-transform"
        />
      </button>

      <Button
        v-if="hasValues"
        size="xs"
        variant="ghost"
        class="h-7 px-2 text-muted-foreground"
        @click="clear"
      >
        <Icon name="i-lucide-x" class="mr-1 h-3 w-3" />
        Clear
      </Button>
    </div>

    <div
      class="grid transition-[grid-template-rows,opacity] duration-300 ease-out"
      :class="open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
      :inert="!open"
      :aria-hidden="!open"
    >
      <div class="grid min-h-0 overflow-hidden">
        <div class="grid gap-3 pt-3 sm:grid-cols-2 lg:grid-cols-3">
      <!-- Location Autocomplete -->
      <ChatLocationAutocomplete v-model="model.location" />

      <!-- Checkin Date -->
      <div class="relative flex items-center" @click="openDatePicker">
        <Icon
          name="i-lucide-calendar"
          class="pointer-events-none absolute left-2.5 h-4 w-4 text-muted-foreground shrink-0"
        />
        <Input
          v-model="model.checkin"
          type="date"
          placeholder="Check-in"
          aria-label="Check-in date"
          class="pl-9 h-9 w-full cursor-pointer bg-background [color-scheme:light] dark:[color-scheme:dark]"
        />
      </div>

      <!-- Nights -->
      <Input
        v-model="nights"
        type="number"
        min="1"
        placeholder="Nights"
        class="h-9 w-full bg-background"
      />

      <!-- Max Price -->
      <div class="relative flex items-center">
        <span class="absolute left-3 text-muted-foreground text-sm font-medium">$</span>
        <Input
          v-model="maxPrice"
          type="number"
          min="0"
          placeholder="Max total price"
          class="pl-7 h-9 w-full bg-background"
        />
      </div>

      <!-- Room Type Select -->
      <Select v-model="model.room_type">
        <SelectTrigger class="h-9 w-full bg-background focus:ring-0 focus:ring-offset-0 text-left">
          <SelectValue placeholder="Room type" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem v-for="item in ROOM_TYPES" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>

      <!-- Minimum Rating -->
      <Input
        v-model="minRating"
        type="number"
        min="1"
        max="5"
        step="0.1"
        placeholder="Minimum rating"
        class="h-9 w-full bg-background"
      />

      <!-- Guests Count -->
      <Input
        v-model="guests"
        type="number"
        min="1"
        max="16"
        placeholder="Guests"
        class="h-9 w-full bg-background"
      />

      <!-- Amenities MultiSelect Popover -->
      <Popover class="sm:col-span-2">
        <PopoverTrigger as-child>
          <Button
            variant="outline"
            class="h-9 w-full sm:col-span-2 bg-background justify-between font-normal text-muted-foreground hover:text-foreground"
          >
            <span class="truncate">{{ selectedAmenitiesLabel }}</span>
            <Icon name="i-lucide-chevron-down" class="h-4 w-4 text-muted-foreground shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" class="w-80 p-0">
          <div class="p-2 border-b border-border">
            <Input
              v-model="amenitiesSearch"
              placeholder="Search amenities..."
              class="h-8 bg-background"
            />
          </div>
          <ScrollArea class="h-60 p-2">
            <div class="space-y-1">
              <div
                v-for="a in filteredAmenities"
                :key="a.value"
                class="flex items-center gap-2.5 w-full text-left px-2.5 py-1.5 rounded-sm hover:bg-accent text-sm cursor-pointer select-none"
                @click="toggleAmenity(a.value)"
              >
                <div
                  class="flex items-center justify-center h-4 w-4 shrink-0 rounded-sm border transition-all"
                  :class="(model.amenities ?? []).includes(a.value) ? 'bg-primary border-primary text-primary-foreground' : 'border-primary/60'"
                >
                  <Icon
                    v-if="(model.amenities ?? []).includes(a.value)"
                    name="i-lucide-check"
                    class="h-3 w-3"
                  />
                </div>
                <span class="truncate text-foreground">{{ a.label }}</span>
              </div>
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>

      <!-- Keywords Input -->
      <div class="flex flex-col gap-2 sm:col-span-2">
        <div class="relative flex items-center">
          <Icon name="i-lucide-search" class="absolute left-2.5 h-4 w-4 text-muted-foreground shrink-0" />
          <Input
            v-model="keywordInput"
            type="text"
            placeholder="Type keyword and press Enter..."
            class="pl-9 h-9 w-full bg-background"
            @keydown.enter.prevent="addKeyword"
          />
        </div>

        <!-- Keywords Badge List -->
        <div v-if="model.keywords?.length" class="flex flex-wrap gap-1.5 pt-1">
          <Badge
            v-for="kw in model.keywords"
            :key="kw"
            variant="secondary"
            class="pl-2.5 pr-1.5 py-1 text-xs font-medium flex items-center gap-1 bg-accent hover:bg-accent/80 text-foreground"
          >
            <span>{{ kw }}</span>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              class="h-4 w-4 rounded-full p-0 text-muted-foreground hover:text-foreground"
              @click="removeKeyword(kw)"
            >
              <Icon name="i-lucide-x" class="h-3 w-3" />
            </Button>
          </Badge>
        </div>
      </div>

      <!-- Match all keywords checkbox -->
      <div class="flex items-center space-x-2">
        <Checkbox
          id="match_all_keywords"
          v-model:checked="model.match_all_keywords"
        />
        <label
          for="match_all_keywords"
          class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer select-none text-muted-foreground hover:text-foreground transition-colors"
        >
          Match all keywords
        </label>
      </div>

      <!-- Checkbox Toggles -->
      <div class="flex flex-wrap items-center gap-4 sm:col-span-2 lg:col-span-3">
        <div class="flex items-center space-x-2">
          <Checkbox id="superhost" v-model:checked="model.superhost" />
          <label for="superhost" class="text-sm font-medium leading-none cursor-pointer select-none text-muted-foreground hover:text-foreground">Superhost</label>
        </div>
        <div class="flex items-center space-x-2">
          <Checkbox id="instant_book" v-model:checked="model.instant_book" />
          <label for="instant_book" class="text-sm font-medium leading-none cursor-pointer select-none text-muted-foreground hover:text-foreground">Instant book</label>
        </div>
        <div class="flex items-center space-x-2">
          <Checkbox id="self_checkin" v-model:checked="model.self_checkin" />
          <label for="self_checkin" class="text-sm font-medium leading-none cursor-pointer select-none text-muted-foreground hover:text-foreground">Self check-in</label>
        </div>
        <div class="flex items-center space-x-2">
          <Checkbox id="use_vision" v-model:checked="model.use_vision" />
          <label for="use_vision" class="text-sm font-medium leading-none cursor-pointer select-none text-muted-foreground hover:text-foreground">Vision re-rank</label>
        </div>
      </div>
        </div>
      </div>
    </div>
  </section>
</template>
