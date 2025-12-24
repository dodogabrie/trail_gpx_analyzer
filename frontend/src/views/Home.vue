<template>
  <div class="space-y-6">
    <div class="bg-white p-6 rounded-lg shadow">
      <h2 class="text-2xl font-bold mb-4">Upload GPX File</h2>

      <div class="mb-4">
        <input
          type="file"
          accept=".gpx"
          @change="handleFileSelect"
          ref="fileInput"
          class="block w-full text-sm text-gray-500
            file:mr-4 file:py-2 file:px-4
            file:rounded file:border-0
            file:text-sm file:font-semibold
            file:bg-blue-50 file:text-blue-700
            hover:file:bg-blue-100"
        />
      </div>

      <button
        @click="uploadFile"
        :disabled="!selectedFile || uploading"
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
      >
        {{ uploading ? 'Uploading...' : 'Upload' }}
      </button>

      <p v-if="gpxStore.error" class="text-red-600 mt-2">{{ gpxStore.error }}</p>
    </div>

    <div v-if="gpxStore.gpxList.length > 0" class="bg-white p-6 rounded-lg shadow">
      <h2 class="text-2xl font-bold mb-4">Your GPX Files</h2>

      <div class="space-y-2">
        <div
          v-for="file in gpxStore.gpxList"
          :key="file.id"
          class="flex justify-between items-center p-3 bg-gray-50 rounded border"
        >
          <div>
            <p class="font-medium">{{ file.original_filename }}</p>
            <p class="text-sm text-gray-600">
              Uploaded: {{ new Date(file.upload_date).toLocaleString() }}
            </p>
          </div>
          <div class="space-x-2">
            <router-link
              :to="`/analysis/${file.id}`"
              class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              Analyze
            </router-link>
            <button
              @click="deleteFile(file.id)"
              class="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!gpxStore.loading" class="bg-white p-6 rounded-lg shadow text-center">
      <p class="text-gray-500">No GPX files uploaded yet. Upload your first file to get started!</p>
    </div>

    <!-- Performance Tracking Card -->
    <div class="bg-white p-6 rounded-lg shadow">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-bold">Performance Tracking</h2>
        <router-link
          to="/performance"
          class="text-sm text-blue-600 hover:text-blue-800 underline"
        >
          View Dashboard
        </router-link>
      </div>

      <div class="space-y-4">
        <p class="text-gray-600">
          Track your running performance over time with weekly snapshots, achievements, and trend analysis.
        </p>

        <div v-if="!authStore.isAuthenticated" class="p-4 bg-yellow-50 border border-yellow-200 rounded">
          <p class="text-sm text-yellow-800 mb-3">Connect your Strava account to track performance and earn achievements.</p>
          <button
            @click="connectStrava"
            class="px-4 py-2 bg-orange-500 text-white rounded hover:bg-orange-600"
          >
            Connect with Strava
          </button>
        </div>

        <div v-else-if="performanceStats" class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="text-center p-3 bg-blue-50 rounded">
            <div class="text-2xl font-bold text-blue-600">{{ performanceStats.total_snapshots || 0 }}</div>
            <div class="text-xs text-gray-600">Weeks Tracked</div>
          </div>
          <div class="text-center p-3 bg-yellow-50 rounded">
            <div class="text-2xl font-bold text-yellow-600">{{ performanceStats.total_achievements || 0 }}</div>
            <div class="text-xs text-gray-600">Achievements</div>
          </div>
          <div class="text-center p-3 bg-green-50 rounded">
            <div class="text-2xl font-bold text-green-600">{{ performanceStats.current_streak || 0 }}</div>
            <div class="text-xs text-gray-600">Week Streak</div>
          </div>
          <div class="text-center p-3 bg-purple-50 rounded">
            <div class="text-2xl font-bold text-purple-600">{{ formatPace(performanceStats.best_flat_pace) }}</div>
            <div class="text-xs text-gray-600">Best Pace</div>
          </div>
        </div>

        <div v-if="authStore.isAuthenticated" class="flex gap-3">
          <button
            @click="refreshPerformanceData"
            :disabled="refreshing"
            class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ refreshing ? 'Refreshing...' : 'Refresh Performance Data' }}
          </button>
          <button
            v-if="performanceStats && performanceStats.total_snapshots > 0"
            @click="$router.push('/performance')"
            class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
          >
            View Dashboard
          </button>
        </div>

        <div v-if="refreshMessage" :class="[
          'p-3 rounded text-sm',
          refreshMessage.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        ]">
          {{ refreshMessage.text }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGpxStore } from '../stores/gpx'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const router = useRouter()
const gpxStore = useGpxStore()
const authStore = useAuthStore()

const fileInput = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)

// Performance tracking state
const performanceStats = ref(null)
const refreshing = ref(false)
const refreshMessage = ref(null)

onMounted(async () => {
  await authStore.checkAuthStatus()
  await gpxStore.fetchGpxList()
  await fetchPerformanceStats()
})

const fetchPerformanceStats = async () => {
  try {
    const response = await api.get('/performance/stats')
    performanceStats.value = response.data
  } catch (error) {
    console.error('Failed to fetch performance stats:', error)
  }
}

const refreshPerformanceData = async () => {
  if (!authStore.isAuthenticated) {
    refreshMessage.value = {
      type: 'error',
      text: 'Please connect your Strava account first.'
    }
    return
  }

  refreshing.value = true
  refreshMessage.value = null

  try {
    const response = await api.post('/performance/refresh', {
      period_type: 'weekly',
      num_periods: 12,
      force_recalculate: false
    })

    refreshMessage.value = {
      type: 'success',
      text: `✓ Created ${response.data.snapshots_created} snapshots! ${response.data.new_achievements?.length || 0} new achievements earned.`
    }
    await fetchPerformanceStats()
  } catch (error) {
    console.error('Refresh failed:', error)
    refreshMessage.value = {
      type: 'error',
      text: 'Failed to refresh performance data. Make sure your Strava account is connected.'
    }
  } finally {
    refreshing.value = false
  }
}

const connectStrava = async () => {
  try {
    const authUrl = await authStore.getStravaAuthUrl()
    window.location.href = authUrl
  } catch (error) {
    console.error('Failed to get Strava auth URL:', error)
  }
}

const formatPace = (paceDecimal) => {
  if (!paceDecimal || !Number.isFinite(paceDecimal)) return 'N/A'
  let mins = Math.floor(paceDecimal)
  let secs = Math.round((paceDecimal - mins) * 60)
  if (secs >= 60) {
    mins += 1
    secs = 0
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const handleFileSelect = (event) => {
  selectedFile.value = event.target.files[0]
}

const uploadFile = async () => {
  if (!selectedFile.value) return

  uploading.value = true
  try {
    const result = await gpxStore.uploadGpx(selectedFile.value)
    router.push(`/analysis/${result.id}`)
  } catch (error) {
    console.error('Upload failed:', error)
  } finally {
    uploading.value = false
    selectedFile.value = null
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const deleteFile = async (id) => {
  if (confirm('Are you sure you want to delete this GPX file?')) {
    await gpxStore.deleteGpx(id)
  }
}
</script>
