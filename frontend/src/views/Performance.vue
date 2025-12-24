<template>
  <div class="container mx-auto px-4 py-6">
    <div class="mb-6">
      <h1 class="text-3xl font-bold">Performance Dashboard</h1>
      <p class="text-gray-600 mt-2">Track your running performance over time</p>
    </div>

    <!-- Overall Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-lg shadow p-4">
        <div class="text-sm text-gray-600">Current Streak</div>
        <div class="text-3xl font-bold text-blue-600">{{ stats.current_streak || 0 }}</div>
        <div class="text-xs text-gray-500">weeks</div>
      </div>

      <div class="bg-white rounded-lg shadow p-4">
        <div class="text-sm text-gray-600">Total Achievements</div>
        <div class="text-3xl font-bold text-yellow-600">{{ stats.total_achievements || 0 }}</div>
        <div class="text-xs text-gray-500">earned</div>
      </div>

      <div class="bg-white rounded-lg shadow p-4">
        <div class="text-sm text-gray-600">Total Distance</div>
        <div class="text-3xl font-bold text-green-600">{{ (stats.total_distance_km || 0).toFixed(0) }}</div>
        <div class="text-xs text-gray-500">km</div>
      </div>

      <div class="bg-white rounded-lg shadow p-4">
        <div class="text-sm text-gray-600">Best Flat Pace</div>
        <div class="text-3xl font-bold text-purple-600">{{ formatPace(stats.best_flat_pace) }}</div>
        <div class="text-xs text-gray-500">/km</div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Performance Trends -->
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">Performance Trends</h2>

        <div class="space-y-4">
          <div v-for="grade in [-30, -20, -10, 0, 10, 20, 30]" :key="grade" class="border-b pb-3 last:border-0">
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium">{{ grade >= 0 ? `+${grade}` : grade }}% Grade</span>
              <span class="text-sm text-gray-600">{{ getGradeLabel(grade) }}</span>
            </div>

            <div v-if="trends[grade] && trends[grade].length > 0" class="space-y-1">
              <div class="flex items-center gap-2">
                <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    class="h-full rounded-full transition-all duration-300"
                    :class="getTrendColor(grade)"
                    :style="{ width: getTrendWidth(grade) + '%' }"
                  ></div>
                </div>
                <span class="text-xs font-medium" :class="getTrendTextColor(grade)">
                  {{ getTrendDirection(grade) }} {{ Math.abs(getTrendPercentage(grade)).toFixed(1) }}%
                </span>
              </div>
              <div class="text-xs text-gray-500">
                {{ formatPace(trends[grade][trends[grade].length - 1]?.pace) }}/km
                ({{ trends[grade][trends[grade].length - 1]?.sample_count }} samples)
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 italic">No data yet</div>
          </div>
        </div>
      </div>

      <!-- Achievements -->
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-semibold">Achievements</h2>
          <span v-if="newAchievementsCount > 0" class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">
            {{ newAchievementsCount }} new
          </span>
        </div>

        <div v-if="achievements.length === 0" class="text-center py-8 text-gray-400">
          <div class="text-4xl mb-2">🏆</div>
          <p>No achievements yet</p>
          <p class="text-sm">Keep training to earn your first badge!</p>
        </div>

        <div v-else class="space-y-3 max-h-[400px] overflow-y-auto">
          <div
            v-for="achievement in achievements"
            :key="achievement.id"
            class="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
            :class="{ 'border-yellow-400 bg-yellow-50': !achievement.notified }"
          >
            <div class="flex items-start gap-3">
              <div class="text-2xl">{{ achievement.icon }} {{ achievement.category_icon }}</div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <h3 class="font-semibold text-sm">{{ achievement.name }}</h3>
                  <span v-if="!achievement.notified" class="bg-yellow-200 text-yellow-800 text-xs px-1.5 py-0.5 rounded">
                    NEW
                  </span>
                </div>
                <p class="text-xs text-gray-600 mt-1">{{ achievement.description }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ formatDate(achievement.earned_at) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Weekly Snapshots -->
    <div class="mt-6 bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-semibold mb-4">Recent Performance</h2>

      <div v-if="snapshots.length === 0" class="text-center py-8 text-gray-400">
        <p>No performance data yet</p>
        <p class="text-sm">Complete activities to start tracking your progress</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left">Period</th>
              <th class="px-4 py-2 text-left">Flat Pace</th>
              <th class="px-4 py-2 text-left">Activities</th>
              <th class="px-4 py-2 text-left">Distance</th>
              <th class="px-4 py-2 text-left">Elevation</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="snapshot in snapshots"
              :key="snapshot.id"
              class="border-t hover:bg-gray-50"
            >
              <td class="px-4 py-2 font-medium">{{ snapshot.period }}</td>
              <td class="px-4 py-2">{{ formatPace(snapshot.flat_pace) }}/km</td>
              <td class="px-4 py-2">{{ snapshot.activity_count }}</td>
              <td class="px-4 py-2">{{ snapshot.total_distance?.toFixed(1) || 0 }} km</td>
              <td class="px-4 py-2">{{ snapshot.total_elevation?.toFixed(0) || 0 }} m</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="mt-6">
      <div class="mb-2 flex flex-wrap items-center gap-2">
        <label class="text-sm text-gray-600" for="fatigue-mode">Fatigue view:</label>
        <select
          id="fatigue-mode"
          v-model="fatigueMode"
          class="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
        >
          <option value="rolling">Rolling window</option>
          <option value="snapshot">Single snapshot</option>
        </select>

        <template v-if="fatigueMode === 'rolling'">
          <label class="text-sm text-gray-600 ml-2" for="fatigue-weeks">Weeks:</label>
          <select
            id="fatigue-weeks"
            v-model.number="rollingWeeks"
            class="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
          >
            <option :value="4">4</option>
            <option :value="8">8</option>
            <option :value="12">12</option>
            <option :value="24">24</option>
          </select>
          <span v-if="rollingFatigueCurve?.meta?.activities_used" class="text-xs text-gray-400 ml-2">
            {{ rollingFatigueCurve.meta.activities_used }} activities
          </span>
          <button
            type="button"
            class="ml-auto text-sm text-blue-600 hover:text-blue-800 underline"
            @click="fetchRollingFatigueCurve"
          >
            Refresh
          </button>
        </template>

        <template v-else>
          <label class="text-sm text-gray-600 ml-2" for="fatigue-period">Period:</label>
          <select
            id="fatigue-period"
            v-model="selectedFatigueSnapshotId"
            class="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
          >
            <option v-for="s in snapshots" :key="s.id" :value="s.id">
              {{ s.period }}{{ s.fatigue_curve ? '' : ' (no curve)' }}
            </option>
          </select>
          <button
            type="button"
            class="ml-auto text-sm text-blue-600 hover:text-blue-800 underline"
            @click="selectedFatigueSnapshotId = snapshotWithFatigueCurve?.id || snapshots[0]?.id"
          >
            Jump to latest with curve
          </button>
        </template>
      </div>
      <FatigueCurveChart :fatigue-curve="effectiveFatigueCurve" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import api from '../services/api'
import FatigueCurveChart from '../components/FatigueCurveChart.vue'

const stats = ref({})
const achievements = ref([])
const snapshots = ref([])
const trends = ref({})
const loading = ref(true)

const snapshotWithFatigueCurve = computed(() => {
  return snapshots.value.find(s => s?.fatigue_curve) || null
})

const selectedFatigueSnapshotId = ref(null)

const selectedFatigueSnapshot = computed(() => {
  const id = selectedFatigueSnapshotId.value
  if (!id) return snapshotWithFatigueCurve.value || snapshots.value[0] || null
  return snapshots.value.find(s => s?.id === id) || null
})

const fatigueMode = ref('rolling') // 'rolling' | 'snapshot'
const rollingWeeks = ref(12)
const rollingFatigueCurve = ref(null)

const effectiveFatigueCurve = computed(() => {
  if (fatigueMode.value === 'rolling') return rollingFatigueCurve.value
  return selectedFatigueSnapshot.value?.fatigue_curve || null
})

const fetchRollingFatigueCurve = async () => {
  try {
    const response = await api.get('/performance/fatigue', { params: { weeks: rollingWeeks.value } })
    rollingFatigueCurve.value = response.data?.fatigue_curve || null
  } catch (error) {
    console.error('Failed to fetch rolling fatigue curve:', error)
    rollingFatigueCurve.value = null
  }
}

const newAchievementsCount = computed(() => {
  return achievements.value.filter(a => !a.notified).length
})

const fetchStats = async () => {
  try {
    const response = await api.get('/performance/stats')
    stats.value = response.data
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

const fetchAchievements = async () => {
  try {
    const response = await api.get('/performance/achievements')
    achievements.value = response.data.achievements || []
  } catch (error) {
    console.error('Failed to fetch achievements:', error)
  }
}

const fetchSnapshots = async () => {
  try {
    const response = await api.get('/performance/snapshots', {
      params: { period_type: 'weekly', limit: 12 }
    })
    snapshots.value = response.data.snapshots || []
    if (!selectedFatigueSnapshotId.value && snapshots.value.length) {
      selectedFatigueSnapshotId.value = (snapshotWithFatigueCurve.value?.id || snapshots.value[0].id)
    }
  } catch (error) {
    console.error('Failed to fetch snapshots:', error)
  }
}

const fetchTrends = async () => {
  const grades = [-30, -20, -10, 0, 10, 20, 30]
  for (const grade of grades) {
    try {
      const response = await api.get('/performance/trends', {
        params: { grade: grade, periods: 12 }
      })
      trends.value[grade] = response.data.trend || []
    } catch (error) {
      console.error(`Failed to fetch trend for grade ${grade}:`, error)
    }
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

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const getGradeLabel = (grade) => {
  if (grade >= 20) return 'Steep Uphill'
  if (grade > 5) return 'Uphill'
  if (grade <= -20) return 'Steep Downhill'
  if (grade < -5) return 'Downhill'
  return 'Flat'
}

const getTrendPercentage = (grade) => {
  const trend = trends.value[grade]
  if (!trend || trend.length < 2) return 0

  const first = trend[0].pace
  const last = trend[trend.length - 1].pace
  return ((last - first) / first) * 100
}

const getTrendDirection = (grade) => {
  const pct = getTrendPercentage(grade)
  if (pct < -2) return '↑'
  if (pct > 2) return '↓'
  return '→'
}

const getTrendColor = (grade) => {
  const pct = getTrendPercentage(grade)
  if (pct < -2) return 'bg-green-500'
  if (pct > 2) return 'bg-red-500'
  return 'bg-gray-400'
}

const getTrendTextColor = (grade) => {
  const pct = getTrendPercentage(grade)
  if (pct < -2) return 'text-green-600'
  if (pct > 2) return 'text-red-600'
  return 'text-gray-600'
}

const getTrendWidth = (grade) => {
  const pct = Math.abs(getTrendPercentage(grade))
  return Math.min(100, (pct / 20) * 100) // Scale to 0-100%, max at 20% change
}

onMounted(async () => {
  loading.value = true
  await Promise.all([
    fetchStats(),
    fetchAchievements(),
    fetchSnapshots(),
    fetchTrends()
  ])
  await fetchRollingFatigueCurve()
  loading.value = false
})

watch([fatigueMode, rollingWeeks], async ([mode]) => {
  if (mode === 'rolling') await fetchRollingFatigueCurve()
})
</script>
