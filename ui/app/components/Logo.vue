<script setup lang="ts">
const colorMode = useColorMode()
const iconSrc = computed(() => colorMode.value === 'dark' ? '/homey-icon-dark.svg' : '/homey-icon-light.svg')
</script>

<template>
  <img
    :src="iconSrc"
    alt=""
    aria-hidden="true"
    class="block max-h-full max-w-full object-contain"
  >
</template>
