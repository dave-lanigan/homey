<script setup lang="ts">
definePageMeta({
  layout: 'auth',
})
</script>

<template>
  <SignIn
    routing="path"
    path="/sign-in"
    sign-up-url="/sign-up"
    fallback-redirect-url="/"
  />
</template>
