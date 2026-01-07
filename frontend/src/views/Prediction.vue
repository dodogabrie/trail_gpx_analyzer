<template>
  <div class="container mx-auto px-4 py-6">
    <AchievementNotification />

    <div class="mb-6">
      <h1 class="text-3xl font-bold">Route Time Prediction</h1>
      <p class="text-gray-600 mt-2">
        Predict your time for
        <strong>{{ gpxStore.currentGpx?.original_filename }}</strong>
      </p>

      <div class="mt-4 flex items-center gap-4">
        <label class="text-sm font-medium text-gray-700">Effort Level:</label>
        <div class="flex gap-2">
          <button
            @click="predictionStore.effort = 'race'"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              predictionStore.effort === 'race'
                ? 'bg-red-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            🏁 Race
          </button>
          <button
            @click="predictionStore.effort = 'training'"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              predictionStore.effort === 'training'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            🏃 Training
          </button>
          <button
            @click="predictionStore.effort = 'recovery'"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              predictionStore.effort === 'recovery'
                ? 'bg-green-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            ]"
          >
            🚶 Recovery
          </button>
        </div>
        <span class="text-xs text-gray-500">
          {{ getEffortDescription(predictionStore.effort) }}
        </span>
      </div>
    </div>

    <div v-if="predictionStore.error" class="bg-red-50 border border-red-200 rounded p-4 mb-6">
      <p class="text-red-600">{{ predictionStore.error }}</p>
      <button
        @click="retryPrediction"
        class="text-red-800 underline text-sm mt-2"
      >
        Retry prediction
      </button>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
      <div v-if="predictionStore.loading" class="text-center py-12">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p class="text-lg font-medium">Generating prediction...</p>
        <p class="text-gray-600 text-sm mb-4">Analyzing route segments with the trained model</p>

        <div class="mt-6 max-w-md mx-auto bg-blue-50 rounded-lg p-4">
          <div class="space-y-2 text-sm text-left">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span class="text-gray-700">Converting GPX to route profile</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
              <span class="text-gray-700">Running hybrid prediction</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
              <span class="text-gray-700">Calculating segment breakdown</span>
            </div>
          </div>
          <div class="mt-4 text-xs text-gray-500 text-center">
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

      <div v-else class="text-center py-12 text-gray-600">
        <p>No prediction yet. Click retry to start.</p>
      </div>
    </div>

    <div class="mt-6">
      <router-link
        to="/"
        class="text-blue-600 hover:text-blue-800"
      >
        ← Back to Home
      </router-link>
    </div>
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
