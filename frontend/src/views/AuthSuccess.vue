<template>
  <div class="card text-center">
    <h2 class="section-title text-emerald-600 mb-4">Authentication Successful!</h2>
    <p class="text-slate-600 mb-4">You have been successfully connected to Strava.</p>
    <p class="text-slate-500">Syncing your Strava activities in the background. Redirecting to home...</p>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  const token = route.query.token

  if (token) {
    authStore.setToken(token)
    await authStore.checkAuthStatus()
  }

  setTimeout(() => {
    router.push('/')
  }, 2000)
})
</script>
