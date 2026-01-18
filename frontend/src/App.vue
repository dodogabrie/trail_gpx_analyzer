<template>
  <div id="app" class="min-h-screen flex flex-col bg-slate-50">
    <!-- Navigation -->
    <nav class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
      <div class="layout flex h-16 items-center justify-between">
        <!-- Logo -->
        <router-link :to="homeRoute" class="flex items-center gap-2 group">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-700 text-white shadow-md group-hover:bg-emerald-800 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
               <path stroke-linecap="round" stroke-linejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
               <path stroke-linecap="round" stroke-linejoin="round" d="M12 18a3.75 3.75 0 00.495-7.467 5.99 5.99 0 00-1.925 3.546 5.974 5.974 0 01-2.133-1.001A3.75 3.75 0 0012 18z" />
            </svg>
          </div>
          <div class="flex flex-col">
            <span class="text-lg font-bold uppercase tracking-tight text-slate-900 leading-none">GPX Analyzer</span>
            <span class="text-[10px] font-bold text-emerald-600 uppercase tracking-widest">Trail Intelligence</span>
          </div>
        </router-link>

        <!-- Navigation Links (Removed) -->
        <div class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600 uppercase tracking-wide">
          <router-link :to="planRoute" class="hover:text-emerald-700 transition-colors">
            {{ $t('nav.plan') }}
          </router-link>
          <router-link :to="howItWorksRoute" class="hover:text-emerald-700 transition-colors">
            {{ $t('nav.methodology') }}
          </router-link>
          <router-link :to="aboutRoute" class="hover:text-emerald-700 transition-colors">
            {{ $t('nav.about') }}
          </router-link>
        </div>

        <!-- Right Side Actions -->
        <div class="flex items-center gap-4">
          <template v-if="authStore.isAuthenticated">
            <div class="hidden sm:flex flex-col items-end mr-2">
              <span class="text-[10px] text-slate-400 uppercase tracking-wider">{{ $t('app.athlete') }}</span>
              <span class="text-xs font-bold text-slate-700">{{ authStore.user?.strava_username }}</span>
            </div>
            <button @click="logout" class="text-slate-400 hover:text-rose-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
            </button>
          </template>
          <template v-else>
            <button @click="connectStrava" class="btn btn-secondary text-xs py-2 px-4 bg-[#FC4C02] hover:bg-[#E34402] text-white border-none shadow-orange-500/20">
              {{ $t('common.buttons.connect_strava') }}
            </button>
          </template>
          <button
            class="md:hidden inline-flex items-center justify-center w-9 h-9 rounded-md border border-slate-200 text-slate-600 hover:text-emerald-700 hover:border-emerald-200 transition-colors"
            @click="mobileMenuOpen = !mobileMenuOpen"
            :aria-expanded="mobileMenuOpen ? 'true' : 'false'"
            aria-label="Toggle navigation"
          >
            <span class="sr-only">Toggle navigation</span>
            <span class="flex flex-col gap-[3px]">
              <span class="block w-5 h-[2px] bg-current rounded"></span>
              <span class="block w-5 h-[2px] bg-current rounded"></span>
              <span class="block w-5 h-[2px] bg-current rounded"></span>
            </span>
          </button>
        </div>
      </div>
      <div v-if="mobileMenuOpen" class="md:hidden border-t border-slate-200 bg-white/95 backdrop-blur-md">
        <div class="layout py-4 flex flex-col gap-3 text-sm font-semibold text-slate-700 uppercase tracking-wide">
          <router-link :to="planRoute" class="hover:text-emerald-700 transition-colors" @click="mobileMenuOpen = false">
            {{ $t('nav.plan') }}
          </router-link>
          <router-link :to="howItWorksRoute" class="hover:text-emerald-700 transition-colors" @click="mobileMenuOpen = false">
            {{ $t('nav.methodology') }}
          </router-link>
          <router-link :to="aboutRoute" class="hover:text-emerald-700 transition-colors" @click="mobileMenuOpen = false">
            {{ $t('nav.about') }}
          </router-link>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-grow w-full layout" :class="isHome ? 'pb-8 md:pb-12' : 'py-8 md:py-12'">
      <div v-if="!isHome" class="mb-4">
        <router-link :to="homeRoute" class="link text-sm">{{ $t('nav.back_home') }}</router-link>
      </div>
      <router-view />
    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-200 bg-white py-8 mt-auto">
      <div class="layout flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-slate-500">
        <div>{{ $t('app.copyright') }}</div>
        <div class="flex gap-6">
          <router-link :to="howItWorksRoute" class="hover:text-emerald-700 transition-colors">
            {{ $t('app.methodology') }}
          </router-link>
          <router-link :to="privacyRoute" class="hover:text-emerald-700 transition-colors">
            {{ $t('app.privacy') }}
          </router-link>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import api from './services/api'

const authStore = useAuthStore()
const route = useRoute()
const { locale } = useI18n()
const mobileMenuOpen = ref(false)

const homeRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  return useLang ? { name: 'Home', params: { lang: langParam } } : { name: 'Home' }
})

const isHome = computed(() => route.name === 'Home')

const planRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  return {
    name: 'Predict',
    params: useLang ? { lang: langParam } : {}
  }
})

const aboutRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  const isItalian = locale.value === 'it'
  return {
    name: isItalian ? 'AboutIt' : 'AboutEn',
    params: useLang ? { lang: langParam } : {}
  }
})

const privacyRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  return {
    name: 'Privacy',
    params: useLang ? { lang: langParam } : {}
  }
})

const howItWorksRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  const isItalian = locale.value === 'it'
  return {
    name: isItalian ? 'HowItWorksIt' : 'HowItWorksEn',
    params: useLang ? { lang: langParam } : {}
  }
})

onMounted(async () => {
  await authStore.checkAuthStatus()
})

const connectStrava = async () => {
  try {
    console.debug('connectStrava: requesting auth URL...')
    const authUrl = await authStore.getStravaAuthUrl()
    console.debug('connectStrava: got auth URL', authUrl)
    window.location.href = authUrl
  } catch (error) {
    const status = error?.response?.status
    const statusText = error?.response?.statusText
    const url = error?.config?.url
    const baseUrl = error?.config?.baseURL || api?.defaults?.baseURL
    const code = error?.code
    const message = error?.message || 'Unknown error'
    const details = [
      'Unable to start Strava login.',
      status ? `Status: ${status}${statusText ? ` ${statusText}` : ''}` : null,
      baseUrl ? `Base URL: ${baseUrl}` : null,
      url ? `URL: ${url}` : null,
      code ? `Code: ${code}` : null,
      `Page: ${window.location.href}`,
      `Message: ${message}`
    ]
      .filter(Boolean)
      .join('\n')
    console.error('connectStrava: failed to get auth URL', error)
    alert(details)
  }
}

const logout = () => {
  authStore.logout()
}
</script>
