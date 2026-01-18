<template>
  <div class="card text-center">
    <h2 class="section-title text-rose-600 mb-4">{{ $t('auth_error.title') }}</h2>
    <p class="text-slate-600 mb-4">{{ errorMessage }}</p>
    <router-link
      :to="homeRoute"
      class="btn btn-primary inline-flex"
    >
      {{ $t('auth_error.cta') }}
    </router-link>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { locale, t } = useI18n()
const errorMessage = ref(t('auth_error.default_message'))
const homeRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  if (useLang) {
    return { name: 'Home', params: { lang: langParam } }
  }
  const storedLang = typeof localStorage === 'undefined' ? null : localStorage.getItem('preferred_lang')
  const fallbackLang = storedLang || locale.value
  if (fallbackLang) {
    return { name: 'Home', params: { lang: fallbackLang } }
  }
  return { name: 'Home' }
})

onMounted(() => {
  const error = route.query.error

  if (error === 'no_code') {
    errorMessage.value = t('auth_error.no_code')
  } else if (error === 'exchange_failed') {
    errorMessage.value = t('auth_error.exchange_failed')
  } else if (error) {
    errorMessage.value = t('auth_error.generic', { error })
  }
})
</script>
