<template>
  <div id="app" class="app-shell">
    <div class="app-glow"></div>

    <nav class="relative z-10">
      <div class="layout flex h-16 items-center justify-between">
        <router-link to="/" class="flex items-center gap-3 text-lg font-semibold uppercase tracking-[0.3em] text-slate-900">
          <span class="badge">GPX</span>
          <span>Analyzer</span>
        </router-link>

        <div class="flex items-center gap-3">
          <template v-if="authStore.isAuthenticated">
            <span class="pill">
              {{ authStore.user?.strava_username || 'Athlete' }}
            </span>
            <button @click="logout" class="btn btn-danger">
              Logout
            </button>
          </template>
          <template v-else>
            <button @click="connectStrava" class="btn btn-signal">
              Connect Strava
            </button>
          </template>
        </div>
      </div>
    </nav>

    <main class="layout page relative z-10">
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
