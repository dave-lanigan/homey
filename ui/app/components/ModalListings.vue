<script setup lang="ts">
import type { ListingResult } from '~~/shared/utils/search'
import { Button } from '~/components/ui/button'

const activeModal = useState<{
  type: string | null
  listings?: ListingResult[]
}>('active-modal')

const listings = computed(() => activeModal.value.listings ?? [])

function close() {
  activeModal.value = { type: null }
}

function formatPercent(value?: number | null) {
  return value == null ? null : `${Math.round(value * 100)}% match`
}
</script>

<template>
  <Dialog :open="true" @update:open="open => !open && close()">
    <DialogScrollContent
      class="flex max-h-[90vh] w-[calc(100vw-2rem)] max-w-6xl flex-col gap-0 overflow-hidden p-0"
    >
      <DialogHeader class="shrink-0 border-b border-border bg-background p-6">
        <DialogTitle>Listing results</DialogTitle>
        <DialogDescription>
          {{ listings.length }} {{ listings.length === 1 ? 'listing' : 'listings' }} matched your search.
        </DialogDescription>
      </DialogHeader>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <div class="grid gap-5 p-6 sm:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="(listing, index) in listings"
            :key="listing.url || index"
            class="overflow-hidden rounded-xl border border-border bg-card shadow-sm"
          >
            <div class="aspect-[4/3] bg-muted">
              <img
                v-if="listing.image_url"
                :src="listing.image_url"
                :alt="listing.title"
                class="h-full w-full object-cover"
                loading="lazy"
              />
              <div v-else class="flex h-full items-center justify-center text-muted-foreground">
                <Icon name="i-lucide-image-off" class="h-8 w-8" />
              </div>
            </div>

            <div class="space-y-3 p-4">
              <div>
                <div class="mb-1 flex items-start justify-between gap-3">
                  <h3 class="line-clamp-2 font-semibold leading-snug">
                    {{ listing.title || 'Untitled listing' }}
                  </h3>
                  <span
                    v-if="formatPercent(listing.match_score)"
                    class="shrink-0 rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary"
                  >
                    {{ formatPercent(listing.match_score) }}
                  </span>
                </div>
                <p v-if="listing.city" class="text-sm text-muted-foreground">
                  <Icon name="i-lucide-map-pin" class="mr-1 inline h-3.5 w-3.5" />
                  {{ listing.city }}
                </p>
              </div>

              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <strong v-if="listing.total_price != null">
                  ${{ Math.round(listing.total_price) }} total
                </strong>
                <strong v-if="listing.price != null">${{ Math.round(listing.price) }}/night</strong>
                <span v-if="listing.rating != null" class="text-muted-foreground">
                  ★ {{ listing.rating }}
                </span>
                <span v-if="listing.vision_score != null" class="text-muted-foreground">
                  Visual {{ Math.round(listing.vision_score * 100) }}%
                </span>
              </div>

              <p v-if="listing.description" class="line-clamp-3 text-sm text-muted-foreground">
                {{ listing.description }}
              </p>

              <div v-if="listing.amenities?.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="amenity in listing.amenities.slice(0, 5)"
                  :key="amenity"
                  class="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                >
                  {{ amenity }}
                </span>
              </div>

              <Button as-child class="w-full">
                <a :href="listing.url" target="_blank" rel="noopener noreferrer">
                  View on Airbnb
                  <Icon name="i-lucide-external-link" class="ml-2 h-4 w-4" />
                </a>
              </Button>
            </div>
          </article>
        </div>
      </div>
    </DialogScrollContent>
  </Dialog>
</template>
