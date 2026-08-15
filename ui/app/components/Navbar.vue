<script setup lang="ts">
import { Button } from '~/components/ui/button'

const colorMode = useColorMode()

function toggleColorMode() {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <header class="absolute top-0 inset-x-0 h-14 border-b border-border/40 z-10 backdrop-blur bg-background/80 flex items-center justify-between px-4">
    <div class="flex items-center gap-3 min-w-0">
      <slot name="title" />
    </div>

    <div class="flex items-center gap-2">
      <slot />

      <Button variant="ghost" size="icon" @click="toggleColorMode" aria-label="Toggle theme">
        <Icon :name="colorMode.value === 'dark' ? 'i-lucide-moon' : 'i-lucide-sun'" class="h-4 w-4" />
      </Button>

      <Show when="signed-out">
        <Button variant="ghost" size="sm" as-child>
          <NuxtLink to="/sign-in">
            Sign in
          </NuxtLink>
        </Button>
        <Button size="sm" as-child>
          <NuxtLink to="/sign-up">
            Sign up
          </NuxtLink>
        </Button>
      </Show>
      <Show when="signed-in">
        <UserButton />
      </Show>

      <Button
        variant="ghost"
        size="icon"
        as-child
        class="lg:hidden"
        aria-label="New chat"
      >
        <NuxtLink to="/">
          <Icon name="i-lucide-circle-plus" class="h-4 w-4" />
        </NuxtLink>
      </Button>
    </div>
  </header>
</template>
