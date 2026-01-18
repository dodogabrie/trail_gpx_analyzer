<template>
  <div class="stack w-full">
    <AchievementNotification />

    <section class="card stack">
      <div>
        <h1 class="section-title">{{ $t('prediction.title') }}</h1>
        <p class="section-subtitle">
        {{ $t('prediction.subtitle') }}
        <strong>{{ gpxStore.currentGpx?.original_filename }}</strong>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-4">
        <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{{ $t('prediction.effort') }}</span>
        <div class="segmented">
          <button
            @click="predictionStore.effort = 'race'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'race' ? 'segment-active' : ''
            ]"
          >
            {{ $t('prediction.efforts.race') }}
          </button>
          <button
            @click="predictionStore.effort = 'training'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'training' ? 'segment-active' : ''
            ]"
          >
            {{ $t('prediction.efforts.training') }}
          </button>
          <button
            @click="predictionStore.effort = 'recovery'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'recovery' ? 'segment-active' : ''
            ]"
          >
            {{ $t('prediction.efforts.recovery') }}
          </button>
        </div>
        <span class="text-xs text-slate-500">
          {{ getEffortDescription(predictionStore.effort) }}
        </span>
      </div>
    </section>

    <div v-if="predictionStore.error" class="alert alert-error">
      <p>{{ predictionStore.error }}</p>
      <button
        @click="retryPrediction"
        class="btn btn-ghost mt-2"
      >
        {{ $t('prediction.retry') }}
      </button>
    </div>

    <div>
      <div v-if="predictionStore.loading" class="card text-center py-12">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-slate-900 mx-auto mb-4"></div>
        <p class="text-lg font-semibold">{{ $t('prediction.loading.title') }}</p>
        <p class="text-sm text-slate-600 mb-4">{{ $t('prediction.loading.subtitle') }}</p>

        <div class="mt-6 max-w-md mx-auto card card-soft">
          <div class="space-y-2 text-sm text-left">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse"></div>
              <span class="text-slate-700">{{ $t('prediction.loading.step1') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
              <span class="text-slate-700">{{ $t('prediction.loading.step2') }}</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
              <span class="text-slate-700">{{ $t('prediction.loading.step3') }}</span>
            </div>
          </div>
          <div class="mt-4 text-xs text-slate-500 text-center">
            {{ $t('prediction.loading.wait') }}
          </div>
        </div>
      </div>

      <div v-else-if="predictionStore.prediction">
        <PredictionResults
          :prediction="predictionStore.prediction"
          :similar-activities="predictionStore.similarActivities"
          :selected-activity="predictionStore.selectedActivity"
        />
      </div>

      <div v-else class="card text-center py-12 text-slate-600">
        <p>{{ $t('prediction.empty') }}</p>
      </div>
    </div>

    <router-link :to="{ name: 'Home', params: { lang: $route.params.lang } }" class="link">
      {{ $t('prediction.back_home') }}
    </router-link>
  </div>
</template>

<script setup>
import { onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useGpxStore } from '../stores/gpx'
import { usePredictionStore } from '../stores/prediction'
import { useAuthStore } from '../stores/auth'
import PredictionResults from '../components/PredictionResults.vue'
import AchievementNotification from '../components/AchievementNotification.vue'

const route = useRoute()
const gpxStore = useGpxStore()
const predictionStore = usePredictionStore()
const authStore = useAuthStore()
const { t } = useI18n()

const gpxId = computed(() => parseInt(route.params.gpxId))

const getEffortDescription = (effort) => {
  return t(`prediction.effort_descriptions.${effort}`)
}

const runPrediction = async () => {
  if (predictionStore.loading) return

  // Load GPX data if not already loaded
  if (!gpxStore.currentGpx || gpxStore.currentGpx.id !== gpxId.value) {
    await gpxStore.fetchGpxData(gpxId.value)
  }

  if (!authStore.isAuthenticated) {
    await authStore.checkAuthStatus()
  }

  if (!authStore.isAuthenticated) {
    predictionStore.error = 'Please connect to Strava first'
    return
  }

  await predictionStore.predictRouteTime(gpxId.value, true)
}

const retryPrediction = async () => {
  predictionStore.error = null
  await runPrediction()
}

onMounted(async () => {
  await runPrediction()
})

watch(() => predictionStore.effort, async () => {
  if (predictionStore.prediction && !predictionStore.loading) {
    await runPrediction()
  }
})
</script>
