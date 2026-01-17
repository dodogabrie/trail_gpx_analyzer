<template>
  <div class="stack">
    <AchievementNotification />

    <section class="card stack">
      <div>
        <h1 class="section-title">Route Time Prediction</h1>
        <p class="section-subtitle">
        Predict your time for
        <strong>{{ gpxStore.currentGpx?.original_filename }}</strong>
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-4">
        <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Effort</span>
        <div class="segmented">
          <button
            @click="predictionStore.effort = 'race'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'race' ? 'segment-active' : ''
            ]"
          >
            🏁 Race
          </button>
          <button
            @click="predictionStore.effort = 'training'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'training' ? 'segment-active' : ''
            ]"
          >
            🏃 Training
          </button>
          <button
            @click="predictionStore.effort = 'recovery'"
            :class="[
              'segment-btn',
              predictionStore.effort === 'recovery' ? 'segment-active' : ''
            ]"
          >
            🚶 Recovery
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
        Retry prediction
      </button>
    </div>

    <div class="card">
      <div v-if="predictionStore.loading" class="text-center py-12">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-slate-900 mx-auto mb-4"></div>
        <p class="text-lg font-semibold">Generating prediction...</p>
        <p class="text-sm text-slate-600 mb-4">Analyzing route segments with the trained model</p>

        <div class="mt-6 max-w-md mx-auto card card-soft">
          <div class="space-y-2 text-sm text-left">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse"></div>
              <span class="text-slate-700">Converting GPX to route profile</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
              <span class="text-slate-700">Running hybrid prediction</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-lime-400 rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
              <span class="text-slate-700">Calculating segment breakdown</span>
            </div>
          </div>
          <div class="mt-4 text-xs text-slate-500 text-center">
            This may take 5-30 seconds depending on route complexity
          </div>
        </div>
      </div>

      <div v-else-if="predictionStore.prediction">
        <PredictionResults
          :prediction="predictionStore.prediction"
          :similar-activities="predictionStore.similarActivities"
          :selected-activity="predictionStore.selectedActivity"
          @recalibrate="retryPrediction"
        />
      </div>

      <div v-else class="text-center py-12 text-slate-600">
        <p>No prediction yet. Click retry to start.</p>
      </div>
    </div>

    <router-link to="/" class="link">
      ← Back to Home
    </router-link>
  </div>
</template>

<script setup>
import { onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useGpxStore } from '../stores/gpx'
import { usePredictionStore } from '../stores/prediction'
import { useAuthStore } from '../stores/auth'
import PredictionResults from '../components/PredictionResults.vue'
import AchievementNotification from '../components/AchievementNotification.vue'

const route = useRoute()
const gpxStore = useGpxStore()
const predictionStore = usePredictionStore()
const authStore = useAuthStore()

const gpxId = computed(() => parseInt(route.params.gpxId))

const getEffortDescription = (effort) => {
  const descriptions = {
    race: 'Aggressive pace - race effort',
    training: 'Realistic pace - normal effort',
    recovery: 'Easy pace - recovery effort'
  }
  return descriptions[effort] || descriptions.training
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
