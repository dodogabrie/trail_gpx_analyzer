<template>
  <div id="app" class="min-h-screen bg-gray-100">
    <nav class="bg-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between h-16">
          <div class="flex items-center space-x-6">
            <router-link to="/" class="text-xl font-bold text-gray-800">
              GPX Analyzer
            </router-link>
          </div>
          <div class="flex items-center space-x-4">
            <template v-if="authStore.isAuthenticated">
              <span class="text-sm text-gray-600">
                {{ authStore.user?.strava_username || 'User' }}
              </span>
              <button
                @click="logout"
                class="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              >
                Logout
              </button>
            </template>
            <template v-else>
              <button
                @click="connectStrava"
                class="px-4 py-2 bg-orange-500 text-white rounded hover:bg-orange-600"
              >
                Connect Strava
              </button>
            </template>
          </div>
        </div>
      </div>
    </nav>

    <main class="max-w-7xl mx-auto py-6 px-4">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  await authStore.checkAuthStatus()
})

const connectStrava = async () => {
  const authUrl = await authStore.getStravaAuthUrl()
  window.location.href = authUrl
}

const logout = () => {
  authStore.logout()
}
</script>
