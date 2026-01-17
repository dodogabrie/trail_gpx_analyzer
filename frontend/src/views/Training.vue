<template>
  <div class="stack">
    <div>
      <h1 class="section-title">AI Training Center</h1>
      <p class="section-subtitle">Tune the engine with your most representative activities.</p>
    </div>

    <!-- Tier Status Card -->
    <div class="card stack">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-bold">Prediction System Status</h2>
        <button
          v-if="tierStatus && tierStatus.activity_count >= 15"
          @click="retrainMLModel"
          :disabled="retraining"
          class="btn btn-dark disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="retraining" class="animate-spin">⟳</span>
          <span v-else>🔄</span>
          {{ retraining ? 'Retraining...' : 'Retrain ML Model' }}
        </button>
      </div>

      <div v-if="tierStatus" class="space-y-6">
        <!-- Current Tier Badge -->
        <div class="flex items-center justify-between">
          <div>
            <span class="text-sm text-slate-600">Current Tier</span>
            <h3 class="text-xl font-bold text-slate-900">{{ formatTier(tierStatus.current_tier) }}</h3>
            <p class="text-sm text-slate-600 mt-1">{{ tierStatus.confidence_level }} confidence</p>
          </div>
          <div class="text-right">
            <span class="text-sm text-slate-600">Activities Downloaded</span>
            <p class="text-3xl font-bold">{{ tierStatus.activity_count }}</p>
          </div>
        </div>

        <!-- Progress Bar -->
        <div v-if="tierStatus.next_tier" class="space-y-2">
          <div class="flex justify-between text-sm text-slate-600">
            <span>Progress to {{ formatTier(tierStatus.next_tier) }}</span>
            <span>{{ tierStatus.activities_needed_for_next_tier }} more needed</span>
          </div>
          <div class="w-full bg-slate-200 rounded-full h-4">
            <div
              class="h-4 rounded-full transition-all duration-500"
              style="background: linear-gradient(120deg, #bef264 0%, #4ade80 45%, #38bdf8 100%);"
              :style="{ width: tierStatus.progress_to_next_tier_pct + '%' }"
            ></div>
          </div>
        </div>

        <!-- Tier Benefits -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
          <div class="border rounded-xl p-4" :class="tierStatus.activity_count >= 0 ? 'border-lime-300 bg-lime-50' : 'border-slate-300'">
            <div class="text-center">
              <div class="text-2xl mb-2">🔬</div>
              <h4 class="font-bold text-sm">Tier 1: Physics</h4>
              <p class="text-xs text-slate-600 mt-1">0+ activities</p>
              <p class="text-xs mt-2">Default physics model</p>
            </div>
          </div>
          <div class="border rounded-xl p-4" :class="tierStatus.activity_count >= 5 ? 'border-lime-300 bg-lime-50' : 'border-slate-300'">
            <div class="text-center">
              <div class="text-2xl mb-2">⚙️</div>
              <h4 class="font-bold text-sm">Tier 2: Personalized</h4>
              <p class="text-xs text-slate-600 mt-1">5+ activities</p>
              <p class="text-xs mt-2">Learned physics parameters</p>
            </div>
          </div>
          <div class="border rounded-xl p-4" :class="tierStatus.activity_count >= 15 ? 'border-lime-300 bg-lime-50' : 'border-slate-300'">
            <div class="text-center">
              <div class="text-2xl mb-2">🤖</div>
              <h4 class="font-bold text-sm">Tier 3: ML Enhanced</h4>
              <p class="text-xs text-slate-600 mt-1">15+ activities</p>
              <p class="text-xs mt-2">AI-powered corrections</p>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-8">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
        <p class="text-slate-600 mt-4">Loading tier status...</p>
      </div>
    </div>

    <!-- Training Activities Management -->
    <div class="card stack">
      <h2 class="text-2xl font-bold mb-4">Training Activities</h2>

      <div v-if="loadingTrainingActivities" class="text-center py-8">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto"></div>
        <p class="text-slate-600 mt-4">Loading training activities...</p>
      </div>

      <div v-else-if="trainingActivities.length === 0" class="text-center py-8">
        <p class="text-slate-600">No activities downloaded yet. Download activities below to start training.</p>
      </div>

      <div v-else class="space-y-4">
        <!-- Summary Stats -->
        <div class="flex flex-col gap-4 sm:flex-row mb-4">
          <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex-1">
            <div class="text-sm text-slate-600">Included in Training</div>
            <div class="text-3xl font-bold text-emerald-700">{{ trainingActivityStats.included_count }}</div>
          </div>
          <div class="rounded-xl border border-slate-200 bg-slate-50 p-4 flex-1">
            <div class="text-sm text-slate-600">Excluded</div>
            <div class="text-3xl font-bold text-slate-700">{{ trainingActivityStats.excluded_count }}</div>
          </div>
          <div class="rounded-xl border border-sky-200 bg-sky-50 p-4 flex-1">
            <div class="text-sm text-slate-600">Total Downloaded</div>
            <div class="text-3xl font-bold text-slate-900">{{ trainingActivityStats.total }}</div>
          </div>
        </div>

        <!-- Activities List -->
        <div class="max-h-96 overflow-y-auto border rounded-lg">
          <table class="w-full">
            <thead class="bg-slate-50 sticky top-0">
              <tr>
                <th class="px-4 py-2 text-left">Date</th>
                <th class="px-4 py-2 text-left">Type</th>
                <th class="px-4 py-2 text-right">Distance</th>
                <th class="px-4 py-2 text-right">D+</th>
                <th class="px-4 py-2 text-right">Segments</th>
                <th class="px-4 py-2 text-center">Weight</th>
                <th class="px-4 py-2 text-center">Training</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="activity in trainingActivities"
                :key="activity.id"
                class="border-b hover:bg-slate-50"
                :class="activity.excluded_from_training ? 'bg-slate-100 opacity-60' : 'bg-white'"
              >
                <td class="px-4 py-2 text-sm">{{ formatDate(activity.activity_date) }}</td>
                <td class="px-4 py-2 text-sm">{{ activity.activity_type }}</td>
                <td class="px-4 py-2 text-right">{{ activity.distance_km.toFixed(1) }} km</td>
                <td class="px-4 py-2 text-right">{{ Math.round(activity.elevation_gain_m) }} m</td>
                <td class="px-4 py-2 text-right text-slate-600">{{ activity.segment_count }}</td>
                <td class="px-4 py-2 text-center text-sm text-slate-600">{{ activity.recency_weight.toFixed(2) }}</td>
                <td class="px-4 py-2 text-center">
                  <button
                    @click="toggleTrainingStatus(activity)"
                    class="btn btn-outline"
                    :class="activity.excluded_from_training
                      ? 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                      : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'"
                  >
                    {{ activity.excluded_from_training ? 'Excluded' : 'Included' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Activity Download Card -->
    <div class="card stack">
      <h2 class="text-2xl font-bold mb-4">Download Training Activities</h2>

      <div v-if="!stravaActivities.length" class="text-center py-8">
        <p class="text-slate-600 mb-4">Connect Strava to download activities</p>
        <button class="btn btn-signal">
          Connect Strava
        </button>
      </div>

      <div v-else class="space-y-4">
        <!-- Quick Actions -->
        <div class="flex gap-3 mb-4 items-center flex-wrap">
          <button
            @click="selectBestRuns(5)"
            class="btn btn-primary"
          >
            🏃 Select 5 Best Runs
          </button>
          <button
            @click="selectBestRuns(15)"
            class="btn btn-primary"
          >
            🏃 Select 15 Best Runs
          </button>
          <button
            @click="selectBestRuns(20)"
            class="btn btn-primary"
          >
            🏃 Select 20 Best Runs
          </button>
          <div class="text-sm text-slate-600">
            (Long trail/runs preferred)
          </div>
          <button
            @click="selectedIds = []"
            class="btn btn-outline"
          >
            Clear
          </button>
          <div class="flex-1"></div>
          <button
            @click="refreshActivities"
            :disabled="loadingActivities"
            class="btn btn-outline disabled:opacity-50"
          >
            <span v-if="loadingActivities" class="animate-spin">⟳</span>
            <span v-else>🔄</span>
            {{ loadingActivities ? 'Refreshing...' : 'Refresh from Strava' }}
          </button>
        </div>

        <!-- Activity List -->
        <div class="max-h-96 overflow-y-auto border rounded-lg">
          <table class="w-full">
            <thead class="bg-slate-50 sticky top-0">
              <tr>
                <th class="px-4 py-2 text-left">
                  <input type="checkbox" @change="toggleAll" :checked="selectedIds.length === sortedActivities.length">
                </th>
                <th class="px-4 py-2 text-left cursor-pointer hover:bg-slate-100" @click="toggleSort('name')">
                  Activity {{ getSortIcon('name') }}
                </th>
                <th class="px-4 py-2 text-left cursor-pointer hover:bg-slate-100" @click="toggleSort('type')">
                  Type {{ getSortIcon('type') }}
                </th>
                <th class="px-4 py-2 text-left cursor-pointer hover:bg-slate-100" @click="toggleSort('date')">
                  Date {{ getSortIcon('date') }}
                </th>
                <th class="px-4 py-2 text-right cursor-pointer hover:bg-slate-100" @click="toggleSort('distance')">
                  Distance {{ getSortIcon('distance') }}
                </th>
                <th class="px-4 py-2 text-right cursor-pointer hover:bg-slate-100" @click="toggleSort('elevation')">
                  D+ {{ getSortIcon('elevation') }}
                </th>
                <th class="px-4 py-2 text-right cursor-pointer hover:bg-slate-100 font-semibold" @click="toggleSort('combo_score')" title="Distance (km) + D+ (m) / 100">
                  Score {{ getSortIcon('combo_score') }}
                </th>
                <th class="px-4 py-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="activity in sortedActivities"
                :key="activity.strava_id"
                class="border-b hover:bg-slate-50"
                :class="getActivityRowClass(activity)"
              >
                <td class="px-4 py-2">
                  <input
                    type="checkbox"
                    :value="activity.strava_id"
                    v-model="selectedIds"
                  >
                </td>
                <td class="px-4 py-2">{{ activity.name }}</td>
                <td class="px-4 py-2">
                  <span :class="getActivityTypeClass(activity)">
                    {{ getActivityTypeLabel(activity) }}
                  </span>
                </td>
                <td class="px-4 py-2 text-sm text-slate-600">{{ formatDate(activity.start_date) }}</td>
                <td class="px-4 py-2 text-right">{{ (activity.distance / 1000).toFixed(1) }} km</td>
                <td class="px-4 py-2 text-right text-slate-700">{{ Math.round(activity.total_elevation_gain || 0) }} m</td>
                <td class="px-4 py-2 text-right font-semibold text-slate-900">{{ activity.combo_score.toFixed(1) }}</td>
                <td class="px-4 py-2 text-center">
                  <span v-if="activity.has_streams" class="text-emerald-600 text-sm">✓ Downloaded</span>
                  <span v-else class="text-slate-400 text-sm">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Results -->
        <div v-if="downloadResults" class="mt-4 space-y-2">
          <div v-if="downloadResults.success.length" class="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
            <p class="font-medium text-emerald-800">✓ {{ downloadResults.success.length }} activities downloaded</p>
          </div>
          <div v-if="downloadResults.skipped.length" class="rounded-xl border border-amber-200 bg-amber-50 p-3">
            <p class="font-medium text-amber-800">⚠ {{ downloadResults.skipped.length }} activities skipped (already downloaded)</p>
          </div>
          <div v-if="downloadResults.failed.length" class="rounded-xl border border-rose-200 bg-rose-50 p-3">
            <p class="font-medium text-rose-800">✗ {{ downloadResults.failed.length }} activities failed</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'

const tierStatus = ref(null)
const stravaActivities = ref([])
const trainingActivities = ref([])
const loadingTrainingActivities = ref(false)
const trainingActivityStats = ref({ total: 0, included_count: 0, excluded_count: 0 })
const selectedIds = ref([])
const loadingActivities = ref(false)
const sortColumn = ref('combo_score')
const sortDirection = ref('desc')
const retraining = ref(false)

// Computed: sorted activities
const sortedActivities = computed(() => {
  if (!stravaActivities.value.length) return []

  // Add combo score to each activity
  const withScores = stravaActivities.value.map(a => ({
    ...a,
    combo_score: (a.distance / 1000) + ((a.total_elevation_gain || 0) / 100)
  }))

  // Sort based on current column
  return withScores.sort((a, b) => {
    let aVal, bVal

    switch (sortColumn.value) {
      case 'name':
        aVal = a.name || ''
        bVal = b.name || ''
        break
      case 'type':
        aVal = a.type || a.sport_type || ''
        bVal = b.type || b.sport_type || ''
        break
      case 'date':
        aVal = new Date(a.start_date).getTime()
        bVal = new Date(b.start_date).getTime()
        break
      case 'distance':
        aVal = a.distance
        bVal = b.distance
        break
      case 'elevation':
        aVal = a.total_elevation_gain || 0
        bVal = b.total_elevation_gain || 0
        break
      case 'combo_score':
      default:
        aVal = a.combo_score
        bVal = b.combo_score
    }

    if (sortDirection.value === 'asc') {
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
    } else {
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    }
  })
})

onMounted(async () => {
  await Promise.all([
    fetchTierStatus(),
    fetchStravaActivities(),
    fetchTrainingActivities()
  ])
})

const fetchTierStatus = async () => {
  try {
    const response = await api.get('/hybrid/tier-status')
    tierStatus.value = response.data
  } catch (error) {
    console.error('Failed to fetch tier status:', error)
  }
}

const fetchStravaActivities = async (forceRefresh = false) => {
  try {
    loadingActivities.value = true
    const params = forceRefresh ? { force_refresh: 'true' } : {}
    const response = await api.get('/strava/activities', { params })
    stravaActivities.value = response.data.activities || []
  } catch (error) {
    console.error('Failed to fetch activities:', error)
  } finally {
    loadingActivities.value = false
  }
}

const refreshActivities = async () => {
  await fetchStravaActivities(true)
}

const fetchTrainingActivities = async () => {
  try {
    loadingTrainingActivities.value = true
    const response = await api.get('/hybrid/training-activities')
    trainingActivities.value = response.data.activities || []
    trainingActivityStats.value = {
      total: response.data.total,
      included_count: response.data.included_count,
      excluded_count: response.data.excluded_count
    }
  } catch (error) {
    console.error('Failed to fetch training activities:', error)
  } finally {
    loadingTrainingActivities.value = false
  }
}

const toggleTrainingStatus = async (activity) => {
  try {
    const response = await api.post(`/hybrid/training-activities/${activity.id}/toggle`)
    activity.excluded_from_training = response.data.excluded_from_training

    // Update stats
    if (response.data.excluded_from_training) {
      trainingActivityStats.value.included_count--
      trainingActivityStats.value.excluded_count++
    } else {
      trainingActivityStats.value.included_count++
      trainingActivityStats.value.excluded_count--
    }
  } catch (error) {
    console.error('Failed to toggle training status:', error)
    alert('Failed to update training status: ' + (error.response?.data?.error || error.message))
  }
}

const retrainMLModel = async () => {
  if (!confirm('Retrain ML model? This will recompute all parameters including effort variance.')) {
    return
  }

  try {
    retraining.value = true
    const response = await api.post('/hybrid/train-ml-model')

    if (response.data.success) {
      alert(
        `Model retrained successfully!\n\n` +
        `Activities: ${response.data.n_activities_used}\n` +
        `Segments: ${response.data.n_segments_trained}\n` +
        `Variance (σ): ${response.data.residual_variance?.toFixed(4) || 'N/A'}\n` +
        `Confidence: ${response.data.confidence_level}`
      )

      // Refresh tier status
      await fetchTierStatus()
    }
  } catch (error) {
    console.error('Failed to retrain ML model:', error)
    alert('Retraining failed: ' + (error.response?.data?.error || error.message))
  } finally {
    retraining.value = false
  }
}

const toggleSort = (column) => {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'desc'
  }
}

const getSortIcon = (column) => {
  if (sortColumn.value !== column) return '⇅'
  return sortDirection.value === 'asc' ? '↑' : '↓'
}

const formatTier = (tier) => {
  const tierMap = {
    'TIER_1_PHYSICS': 'Physics Baseline',
    'TIER_2_PARAMETER_LEARNING': 'Personalized Physics',
    'TIER_3_RESIDUAL_ML': 'ML Enhanced'
  }
  return tierMap[tier] || tier
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const getActivityTypeLabel = (activity) => {
  const type = activity.type || activity.sport_type || 'Unknown'
  return type.replace('Run', '').trim() || 'Run'
}

const getActivityTypeClass = (activity) => {
  const type = (activity.type || activity.sport_type || '').toLowerCase()
  if (type.includes('trail')) {
    return 'px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-semibold'
  } else if (type.includes('run')) {
    return 'px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-semibold'
  } else {
    return 'px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs'
  }
}

const getActivityRowClass = (activity) => {
  const type = (activity.type || activity.sport_type || '').toLowerCase()
  if (type.includes('trail')) {
    return 'bg-green-50'
  } else if (type.includes('run')) {
    return 'bg-blue-50'
  }
  return ''
}

const selectBestRuns = (count) => {
  // Filter for Run/TrailRun activities only
  const runs = sortedActivities.value.filter(a => {
    const type = a.type || a.sport_type || ''
    return type.toLowerCase().includes('run')
  })

  // Sort by priority:
  // 1. Trail runs first (better terrain variety)
  // 2. Higher combo score (distance + elevation)
  const sortedRuns = runs.sort((a, b) => {
    const aType = (a.type || a.sport_type || '').toLowerCase()
    const bType = (b.type || b.sport_type || '').toLowerCase()

    const aIsTrail = aType.includes('trail')
    const bIsTrail = bType.includes('trail')

    // Trail runs first
    if (aIsTrail && !bIsTrail) return -1
    if (!aIsTrail && bIsTrail) return 1

    // Then by combo score (higher first)
    return b.combo_score - a.combo_score
  })

  selectedIds.value = sortedRuns
    .slice(0, count)
    .map(a => a.strava_id)

  const trailCount = sortedRuns.slice(0, count).filter(a => (a.type || '').toLowerCase().includes('trail')).length
  console.log(`Selected ${selectedIds.value.length} best runs (${trailCount} trails, avg score: ${(sortedRuns.slice(0, count).reduce((sum, a) => sum + a.combo_score, 0) / count).toFixed(1)})`)
}

const toggleAll = (event) => {
  if (event.target.checked) {
    selectedIds.value = sortedActivities.value.map(a => a.strava_id)
  } else {
    selectedIds.value = []
  }
}
</script>
