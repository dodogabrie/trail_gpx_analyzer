<template>
  <div class="text-center py-12">
    <h2 class="text-2xl font-bold text-red-600 mb-4">Authentication Failed</h2>
    <p class="text-gray-600 mb-4">{{ errorMessage }}</p>
    <router-link
      to="/"
      class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 inline-block"
    >
      Return to Home
    </router-link>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const errorMessage = ref('An error occurred during authentication.')

onMounted(() => {
  const error = route.query.error

  if (error === 'no_code') {
    errorMessage.value = 'No authorization code was received from Strava.'
  } else if (error === 'exchange_failed') {
    errorMessage.value = 'Failed to exchange authorization code for access token.'
  } else if (error) {
    errorMessage.value = `Error: ${error}`
  }
})
</script>
