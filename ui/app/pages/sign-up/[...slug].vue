<script setup lang="ts">
definePageMeta({
  layout: 'auth',
})
</script>

<template>
  <SignUp
    routing="path"
    path="/sign-up"
    sign-in-url="/sign-in"
    fallback-redirect-url="/"
  />
</template>
