<template>
  <div>
    <section class="py-12 md:py-20">
      <div class="layout max-w-3xl">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-widest">
          {{ $t('privacy.badge') }}
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-slate-900 mt-6">
          {{ $t('privacy.title') }}
        </h1>

        <div class="mt-8 space-y-6 text-slate-600 leading-relaxed">
          <p>{{ $t('privacy.body1') }}</p>
          <p>{{ $t('privacy.body2') }}</p>
          <p>{{ $t('privacy.body3') }}</p>
          <p class="pt-2">
            <router-link :to="contactRoute" class="link">{{ $t('privacy.contact_link') }}</router-link>
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { locale } = useI18n()

const contactRoute = computed(() => {
  const langParam = route.params.lang
  const useLang = typeof langParam === 'string' && langParam.length > 0
  const isItalian = locale.value === 'it'
  return {
    name: isItalian ? 'AboutIt' : 'AboutEn',
    params: useLang ? { lang: langParam } : {}
  }
})
</script>
