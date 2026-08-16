<script setup lang="ts">
import { Toaster } from '~/components/ui/sonner'
import { TooltipProvider } from '~/components/ui/tooltip'

const colorMode = useColorMode()

const color = computed(() => colorMode.value === 'dark' ? '#0a1016' : '#ffffff')

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
    { key: 'theme-color', name: 'theme-color', content: color },
    { name: 'mobile-web-app-capable', content: 'yes' },
    { name: 'apple-mobile-web-app-capable', content: 'yes' },
    { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
    { name: 'apple-mobile-web-app-title', content: 'Homey' },
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' },
    { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' },
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
  <VitePwaManifest />
  <TooltipProvider :delay-duration="200">
    <NuxtLoadingIndicator color="var(--primary)" />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>

    <Toaster />
  </TooltipProvider>
  <div
    aria-hidden="true"
    class="pointer-events-none fixed inset-0 z-[60] opacity-[0.018] motion-reduce:hidden"
    style="background-image: url(&quot;data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E&quot;); background-repeat: repeat;"
  />
</template>
