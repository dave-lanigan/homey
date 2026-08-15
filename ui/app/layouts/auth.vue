<script setup lang="ts">
import { Button } from '~/components/ui/button'

const colorMode = useColorMode()

function toggleColorMode() {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <div class="relative min-h-screen flex flex-col bg-background text-foreground overflow-hidden">
    <div
      class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--muted)_0%,_transparent_55%)] opacity-70"
      aria-hidden="true"
    />

    <header class="relative z-10 flex items-center justify-between px-4 sm:px-6 h-14">
      <NuxtLink to="/" class="flex items-end gap-1.5 text-foreground">
        <Logo class="h-7 w-auto shrink-0 text-primary" />
        <span class="text-lg font-bold tracking-tight">Homey</span>
      </NuxtLink>

      <Button variant="ghost" size="icon" aria-label="Toggle theme" @click="toggleColorMode">
        <Icon :name="colorMode.value === 'dark' ? 'i-lucide-moon' : 'i-lucide-sun'" class="h-4 w-4" />
      </Button>
    </header>

    <main class="relative z-10 flex-1 flex flex-col items-center justify-center px-4 pb-16 pt-4">
      <slot />
    </main>
  </div>
</template>
