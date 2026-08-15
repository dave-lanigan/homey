<script setup lang="ts">
import type { NuxtError } from '#app'
import { Button } from '~/components/ui/button'

defineProps<{
  error: NuxtError
}>()

useSeoMeta({
  title: 'Page not found',
  description: 'We are sorry but this page could not be found.'
})

useHead({
  htmlAttrs: {
    lang: 'en'
  }
})
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-screen bg-background text-foreground p-4">
    <div class="max-w-md text-center space-y-4">
      <h1 class="text-6xl font-extrabold tracking-tight">{{ error?.statusCode || 404 }}</h1>
      <h2 class="text-2xl font-bold tracking-tight">{{ error?.statusMessage || 'An error occurred' }}</h2>
      <p class="text-muted-foreground">{{ error?.message || 'We apologize, but something went wrong.' }}</p>
      <div class="pt-4">
        <Button @click="clearError({ redirect: '/' })">
          Go back home
        </Button>
      </div>
    </div>
  </div>
</template>
