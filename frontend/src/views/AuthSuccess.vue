<template>
  <div class="card text-center space-y-6">
    <div class="space-y-2">
      <h2 class="section-title text-emerald-600">{{ $t('auth_success.title') }}</h2>
      <p class="text-slate-600">{{ $t('auth_success.subtitle') }}</p>
      <p class="text-slate-500">{{ $t('auth_success.note') }}</p>
    </div>

    <div class="space-y-3 text-left">
      <div class="flex items-center justify-between text-xs text-slate-500 uppercase tracking-widest">
        <span>{{ $t('auth_success.status_label') }}</span>
        <span v-if="syncStatus">{{ formatStatus(syncStatus.status) }}</span>
      </div>
      <div class="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
        <div
          class="h-3 rounded-full transition-all duration-500"
          style="background: linear-gradient(120deg, #34d399 0%, #22d3ee 100%);"
          :style="{ width: `${progressPercent}%` }"
        ></div>
      </div>
      <div class="text-sm text-slate-600">
        <span v-if="syncStatus?.message">{{ syncStatus.message }}</span>
        <span v-else>{{ $t('auth_success.preparing') }}</span>
      </div>
      <div v-if="syncStatus?.total_activities" class="text-xs text-slate-500">
        {{ $t('auth_success.activities_downloaded', { downloaded: syncStatus.downloaded_activities, total: syncStatus.total_activities }) }}
      </div>
      <div v-if="syncStatus?.status === 'completed'" class="text-sm text-emerald-600 font-semibold">
        {{ $t('auth_success.completed') }}
      </div>
      <div v-if="syncStatus?.status === 'error'" class="text-sm text-rose-600 font-semibold">
        {{ $t('auth_success.failed') }}
      </div>
      <div v-if="syncError" class="text-xs text-rose-600">{{ syncError }}</div>
    </div>

    <div class="flex flex-col sm:flex-row gap-3 justify-center">
      <button @click="goHome" class="btn btn-primary px-6">
        {{ $t('auth_success.cta_home') }}
      </button>
      <button @click="checkNow" class="btn btn-outline px-6" :disabled="polling">
        {{ polling ? $t('auth_success.cta_refreshing') : $t('auth_success.cta_refresh') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()
const authStore = useAuthStore()
const syncStatus = ref(null)
const syncError = ref(null)
const polling = ref(false)
let pollTimer = null

const progressPercent = computed(() => syncStatus.value?.progress_percent ?? 0)

const formatStatus = (status) => {
  if (!status) return t('auth_success.status_initializing')
  return status.replace('_', ' ')
}

const goHome = () => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  if (useLang) {
    router.push({ name: 'Home', params: { lang: langParam } })
    return
  }
  const storedLang = typeof localStorage === 'undefined' ? null : localStorage.getItem('preferred_lang')
  const fallbackLang = storedLang || locale.value
  if (fallbackLang) {
    router.push({ name: 'Home', params: { lang: fallbackLang } })
    return
  }
  router.push({ name: 'Home' })
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const fetchSyncStatus = async ({ silent = false } = {}) => {
  if (!silent) {
    polling.value = true
  }
  syncError.value = null
  try {
    const response = await api.get('/strava/sync-status')
    syncStatus.value = response.data
    if (response.data.status === 'completed') {
      stopPolling()
      setTimeout(() => {
        goHome()
      }, 1500)
    }
    if (response.data.status === 'error') {
      stopPolling()
    }
  } catch (error) {
    syncError.value = error.response?.data?.error || t('auth_success.fetch_error')
  } finally {
    if (!silent) {
      polling.value = false
    }
  }
}

const checkNow = async () => {
  await fetchSyncStatus({ silent: false })
}

onMounted(async () => {
  const token = route.query.token

  if (token) {
    authStore.setToken(token)
    await authStore.checkAuthStatus()
  }

  await fetchSyncStatus({ silent: false })
  pollTimer = setInterval(() => fetchSyncStatus({ silent: true }), 2000)
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>
