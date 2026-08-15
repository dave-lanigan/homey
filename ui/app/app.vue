<script setup lang="ts">
import { Toaster } from '~/components/ui/sonner'
import { TooltipProvider } from '~/components/ui/tooltip'

const colorMode = useColorMode()

const color = computed(() => colorMode.value === 'dark' ? '#1b1718' : 'white')

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: 'en'
  }
})

const title = 'Homey'
const description = 'Homey — your friendly AI Airbnb assistant, helping you find the perfect stay.'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description,
  twitterCard: 'summary_large_image'
})
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <NuxtLoadingIndicator color="var(--primary)" />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>

    <Toaster />
  </TooltipProvider>
</template>
