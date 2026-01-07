<template>
  <div class="bg-white rounded-lg shadow p-6">
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 class="text-xl font-semibold">Fatigue Curve</h2>
        <p class="text-sm text-gray-600 mt-1">
          Pace degradation factor vs distance (each band normalized to 1.0 at its first point)
        </p>
      </div>
      <div v-if="maxDistanceKm" class="text-sm text-gray-600 whitespace-nowrap">
        Max distance: <span class="font-semibold text-gray-900">{{ maxDistanceKm.toFixed(0) }} km</span>
      </div>
    </div>

    <div v-if="!hasData" class="text-center py-10 text-gray-400">
      <p>No fatigue curve data yet</p>
      <p class="text-sm">Generate snapshots (Home → “Refresh Performance Data”) to compute it.</p>
    </div>

      <div v-else>
        <div class="flex flex-wrap items-center gap-2 mb-3">
        <span class="text-xs font-semibold text-gray-600 mr-1">Terrain:</span>
        <button
          v-for="grade in suggestedGrades"
          :key="grade"
          type="button"
          class="text-xs px-2 py-1 rounded border transition-colors"
          :class="selectedGradesSet.has(grade) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
          @click="toggleGrade(grade)"
        >
          {{ formatGrade(grade) }}
        </button>
        <span class="text-xs text-gray-400 ml-auto">
          Distances: {{ samplePointsLabel }} <span v-if="minActivitiesNote">· {{ minActivitiesNote }}</span>
        </span>
      </div>

      <div class="h-[320px]">
        <v-chart ref="chartRef" :option="chartOption" autoresize class="w-full h-full" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const props = defineProps({
  fatigueCurve: { type: Object, required: false, default: null }
})

const chartRef = ref(null)

const DEFAULT_BANDS = [
  { key: 'vertical_downhill', label: 'Vertical Downhill' },
  { key: 'downhill', label: 'Downhill' },
  { key: 'flat', label: 'Flat' },
  { key: 'uphill', label: 'Uphill' },
  { key: 'vertical_uphill', label: 'Vertical Uphill' }
]

const legacyBandsFromGrades = computed(() => {
  const grades = props.fatigueCurve?.grades
  if (!grades || typeof grades !== 'object') return null

  const pick = (k) => grades?.[String(k)] || null
  const merge = (entries) => {
    const valid = entries.filter(Boolean)
    if (!valid.length) return null
    const maxLen = Math.max(...valid.map((e) => (e.degradation || []).length))
    const degradation = Array.from({ length: maxLen }, (_, idx) => {
      const vals = valid.map((e) => e.degradation?.[idx]).filter((v) => v !== null && v !== undefined)
      if (!vals.length) return null
      const nums = vals.map((v) => Number(v)).filter(Number.isFinite)
      if (!nums.length) return null
      nums.sort((a, b) => a - b)
      return nums[Math.floor(nums.length / 2)]
    })
    const counts = Array.from({ length: maxLen }, (_, idx) => {
      const vals = valid.map((e) => e.counts?.[idx]).filter((v) => Number.isFinite(Number(v))).map((v) => Number(v))
      if (!vals.length) return null
      return vals.reduce((a, b) => a + b, 0)
    })
    return { degradation, counts }
  }

  return {
    flat: pick(0),
    uphill: pick(10),
    downhill: pick(-10),
    vertical_uphill: merge([pick(20), pick(30)]),
    vertical_downhill: merge([pick(-20), pick(-30)])
  }
})

const bandsData = computed(() => {
  const bands = props.fatigueCurve?.bands
  const overall = props.fatigueCurve?.overall
  if (bands && typeof bands === 'object' && Object.keys(bands).length) {
    return overall ? { overall, ...bands } : bands
  }
  const legacy = legacyBandsFromGrades.value
  if (legacy && Object.values(legacy).some(Boolean)) return legacy
  return null
})

const hasData = computed(() => {
  return Boolean(
    props.fatigueCurve &&
      (Array.isArray(props.fatigueCurve.sample_distances) && props.fatigueCurve.sample_distances.length > 0) &&
      bandsData.value &&
      Object.keys(bandsData.value).length > 0
  )
})

const maxDistanceKm = computed(() => {
  const value = Number(props.fatigueCurve?.max_distance_km)
  return Number.isFinite(value) ? value : null
})

const minActivitiesNote = computed(() => {
  const n = Number(props.fatigueCurve?.meta?.min_activities_per_point)
  return Number.isFinite(n) ? `requires ≥${n} activities/point` : null
})

const sampleDistances = computed(() => {
  return (props.fatigueCurve?.sample_distances || []).map((v) => Number(v)).filter(Number.isFinite)
})

const samplePointsLabel = computed(() => {
  const xs = sampleDistances.value
  if (!xs.length) return '—'
  return xs.map((x) => `${x.toFixed(0)} km`).join(' · ')
})

const availableGrades = computed(() => {
  return Object.keys(bandsData.value || {})
})

const suggestedGrades = computed(() => {
  const order = ['overall', 'flat', 'uphill', 'vertical_uphill', 'downhill', 'vertical_downhill']
  const available = new Set(availableGrades.value)
  const picked = order.filter((k) => available.has(k))
  if (picked.length) return picked
  return availableGrades.value
})

const selectedGrades = ref([])

watch(
  () => suggestedGrades.value,
  (next) => {
    if (selectedGrades.value.length) return
    selectedGrades.value = next.includes('overall') ? ['overall'] : next.slice(0, 3)
  },
  { immediate: true }
)

const selectedGradesSet = computed(() => new Set(selectedGrades.value))

const toggleGrade = (grade) => {
  const current = new Set(selectedGrades.value)
  if (current.has(grade)) {
    current.delete(grade)
  } else {
    current.add(grade)
  }
  selectedGrades.value = Array.from(current)
}

const formatGrade = (key) => {
  if (key === 'overall') return 'Overall'
  const bands = props.fatigueCurve?.meta?.grade_bands || []
  const hit = (bands || []).find((b) => b?.key === key)
  if (hit?.label) return hit.label
  const fallback = DEFAULT_BANDS.find((b) => b.key === key)?.label
  return fallback || String(key)
}

const getSeriesData = (grade) => {
  const entry = (bandsData.value || {})[String(grade)]
  const degradations = entry?.fit?.values || entry?.degradation || entry?.degradations
  if (!Array.isArray(degradations)) return []
  return degradations.map((v) => {
    if (v === null || v === undefined) return null
    const n = Number(v)
    if (!Number.isFinite(n)) return null
    // Convert ratio to "degradation" percentage:
    // ratio 1.25 => -25% (slower), ratio 0.90 => +10% (faster)
    return (1 - n) * 100
  })
}

const getSeriesCounts = (grade) => {
  const entry = (bandsData.value || {})[String(grade)]
  const counts = entry?.counts
  return Array.isArray(counts) ? counts : []
}

const colors = ['#2563eb', '#16a34a', '#dc2626', '#7c3aed', '#0ea5e9']

const forceResize = async () => {
  await nextTick()
  const chart = chartRef.value?.getEChartsInstance?.()
  chart?.resize?.()
}

onMounted(() => {
  if (hasData.value) forceResize()
})

watch(
  () => hasData.value,
  (next) => {
    if (next) forceResize()
  }
)

const chartOption = computed(() => {
  const xs = sampleDistances.value
  const grades = selectedGrades.value
  const series = grades.map((g, idx) => ({
    name: formatGrade(g),
    type: 'line',
    connectNulls: false,
    showSymbol: false,
    lineStyle: { width: 3, color: colors[idx % colors.length] },
    itemStyle: { color: colors[idx % colors.length] },
    data: getSeriesData(g).map((y, i) => [xs[i], y])
  }))

  return {
    grid: { left: 48, right: 20, top: 24, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const axisValue = items[0]?.axisValue
        const axisLabel = Number.isFinite(Number(axisValue)) ? `${Number(axisValue).toFixed(0)} km` : ''
        const lines = [axisLabel]
        for (const p of items) {
          const value = Array.isArray(p?.data) ? p.data[1] : p?.data
          const dataIndex = p?.dataIndex ?? -1
          const seriesKey = selectedGrades.value.find((k) => formatGrade(k) === p?.seriesName)
          const counts = seriesKey ? getSeriesCounts(seriesKey) : []
          const n = Number.isFinite(Number(counts?.[dataIndex])) ? Number(counts[dataIndex]) : null
          const vStr =
            (value === null || value === undefined)
              ? '—'
              : `${Number(value).toFixed(1)}%`
          const nStr = n !== null ? ` (n=${n})` : ''
          lines.push(`${p.marker}${p.seriesName}: ${vStr}${nStr}`)
        }
        return lines.join('<br/>')
      }
    },
    legend: { bottom: 0 },
    xAxis: {
      type: 'value',
      min: xs.length ? xs[0] : undefined,
      max: xs.length ? xs[xs.length - 1] : undefined,
      axisLabel: { color: '#6b7280' },
      axisTick: { show: true },
      axisLine: { show: true },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      min: (val) => {
        const minV = Number(val?.min)
        if (!Number.isFinite(minV)) return -30
        // Round down a bit for padding.
        return Math.floor(minV / 5) * 5
      },
      max: (val) => {
        const maxV = Number(val?.max)
        if (!Number.isFinite(maxV)) return 10
        return Math.ceil(maxV / 5) * 5
      },
      axisLabel: {
        color: '#6b7280',
        formatter: (v) => `${Number(v).toFixed(0)}%`
      },
      splitLine: { lineStyle: { color: '#e5e7eb' } }
    },
    series
  }
})
</script>
