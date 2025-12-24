<template>
  <div class="container mx-auto px-4 py-6">
    <!-- Achievement Notifications -->
    <AchievementNotification />

    <div class="mb-6">
      <h1 class="text-3xl font-bold">Route Time Prediction</h1>
      <p class="text-gray-600 mt-2">
        Predict your time for
        <strong>{{ gpxStore.currentGpx?.original_filename }}</strong>
      </p>
    </div>

    <!-- Error Display -->
    <div v-if="predictionStore.error" class="bg-red-50 border border-red-200 rounded p-4 mb-6">
      <p class="text-red-600">{{ predictionStore.error }}</p>
      <button
        @click="predictionStore.error = null"
        class="text-red-800 underline text-sm mt-2"
      >
        Dismiss
      </button>
    </div>

    <!-- Step Indicator -->
    <div class="mb-8">
      <div class="flex items-center justify-between">
        <div
          v-for="(step, index) in steps"
          :key="step.key"
          :class="[
            'flex-1 text-center pb-2',
            index < steps.length - 1 ? 'border-r' : '',
            isStepActive(step.key) ? 'border-b-2 border-blue-500' : 'border-b-2 border-gray-200'
          ]"
        >
          <div :class="isStepActive(step.key) ? 'text-blue-600 font-semibold' : 'text-gray-400'">
            {{ step.label }}
          </div>
        </div>
      </div>
    </div>

    <!-- Content Area -->
    <div class="bg-white rounded-lg shadow p-6">
      <!-- Step 1: Select Activity -->
      <div v-if="predictionStore.currentStep === 'select-activity'">
        <ActivitySelector
          :gpx-id="gpxId"
        />
      </div>

      <!-- Step 2: Calibrating (Loading) -->
      <div v-else-if="predictionStore.currentStep === 'calibrating'" class="text-center py-12">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p class="text-lg font-medium">Calibrating from activity...</p>
        <p class="text-gray-600 text-sm mb-4">Analyzing pace data</p>

        <!-- Progress Details -->
        <div class="mt-6 max-w-md mx-auto bg-blue-50 rounded-lg p-4">
          <div class="space-y-2 text-sm text-left">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span class="text-gray-700">Downloading activity streams from Strava</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.3s"></div>
              <span class="text-gray-700">Computing flat pace from terrain</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.6s"></div>
              <span class="text-gray-700">Extracting anchor points for personalization</span>
            </div>
          </div>
          <div class="mt-4 text-xs text-gray-500 text-center">
            First-time downloads may take a few seconds
          </div>
        </div>
      </div>

      <!-- Step 3: Review/Edit Calibration -->
      <div v-else-if="predictionStore.currentStep === 'edit-calibration'">
        <CalibrationEditor
          :flat-pace="predictionStore.flatPace"
          :anchor-ratios="predictionStore.editedAnchorRatios || {}"
          :global-curve="predictionStore.globalCurve || []"
          :diagnostics="predictionStore.calibrationDiagnostics || {}"
          :calibration-activity-streams="predictionStore.calibrationActivityStreams || {}"
          @save="onCalibrationSaved"
          @skip="onCalibrationSkipped"
        />
      </div>

      <!-- Step 3: Predicting (Loading) -->
      <div v-else-if="predictionStore.currentStep === 'predicting'" class="text-center py-12">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p class="text-lg font-medium">Generating prediction...</p>
        <p class="text-gray-600 text-sm mb-4">Analyzing route segments with ML model</p>

        <!-- Progress Details -->
        <div class="mt-6 max-w-md mx-auto bg-blue-50 rounded-lg p-4">
          <div class="space-y-2 text-sm text-left">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span class="text-gray-700">Converting GPX to route profile (50m segments)</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.2s"></div>
              <span class="text-gray-700">Running ML prediction model</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.4s"></div>
              <span class="text-gray-700">Calculating segment breakdown</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style="animation-delay: 0.6s"></div>
              <span class="text-gray-700">Filtering similar activities</span>
            </div>
          </div>
          <div class="mt-4 text-xs text-gray-500 text-center">
            This may take 5-30 seconds depending on route complexity
          </div>
        </div>
      </div>

      <!-- Step 4: Results -->
      <div v-else-if="predictionStore.currentStep === 'results'">
        <PredictionResults
          :prediction="predictionStore.prediction"
          :similar-activities="predictionStore.similarActivities"
          :selected-activity="predictionStore.selectedActivity"
          @recalibrate="recalibrate"
        />
      </div>
    </div>

    <!-- Back Button -->
    <div class="mt-6">
      <router-link
        :to="`/analysis/${gpxId}`"
        class="text-blue-600 hover:text-blue-800"
      >
        ← Back to Analysis
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useGpxStore } from '../stores/gpx'
import { usePredictionStore } from '../stores/prediction'
import { useAuthStore } from '../stores/auth'
import ActivitySelector from '../components/ActivitySelector.vue'
import CalibrationEditor from '../components/CalibrationEditor.vue'
import PredictionResults from '../components/PredictionResults.vue'
import AchievementNotification from '../components/AchievementNotification.vue'

const route = useRoute()
const gpxStore = useGpxStore()
const predictionStore = usePredictionStore()
const authStore = useAuthStore()

const gpxId = computed(() => parseInt(route.params.gpxId))

const steps = [
  { key: 'select-activity', label: '1. Select Calibration' },
  { key: 'calibrating', label: '2. Calibrate' },
  { key: 'edit-calibration', label: '3. Review & Edit' },
  { key: 'predicting', label: '4. Predict' },
  { key: 'results', label: '5. Results' }
]

const isStepActive = (stepKey) => {
  const currentIndex = steps.findIndex(s => s.key === predictionStore.currentStep)
  const stepIndex = steps.findIndex(s => s.key === stepKey)
  return stepIndex <= currentIndex
}

onMounted(async () => {
  // Load GPX data if not already loaded
  if (!gpxStore.currentGpx || gpxStore.currentGpx.id !== gpxId.value) {
    await gpxStore.fetchGpxData(gpxId.value)
  }

  // Check Strava authentication
  if (!authStore.isAuthenticated) {
    predictionStore.error = 'Please connect to Strava first'
    return
  }

  // Fetch calibration activities
  await predictionStore.fetchCalibrationActivities(gpxId.value)
})

const onCalibrationSaved = async (editedData) => {
  try {
    await predictionStore.saveCalibration(editedData)
  } finally {
    await predictionStore.predictRouteTime(gpxId.value)
  }
}

const onCalibrationSkipped = async () => {
  await predictionStore.predictRouteTime(gpxId.value)
}

const recalibrate = () => {
  predictionStore.reset()
  predictionStore.fetchCalibrationActivities(gpxId.value)
}
</script>
