<template>
  <div class="bg-white rounded-lg shadow p-6">
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 class="text-xl font-semibold">Model Comparison</h2>
        <p class="text-sm text-gray-600 mt-1">
          How the 3 model tiers predict your pace across different grades.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1 text-xs text-gray-500">
          <span class="w-3 h-0.5 bg-gray-400 border-dashed"></span>
          <span>Tier 1 (Physics)</span>
        </div>
        <div class="flex items-center gap-1 text-xs text-blue-600">
          <span class="w-3 h-0.5 bg-blue-600"></span>
          <span>Tier 2 (Learned)</span>
        </div>
        <div class="flex items-center gap-1 text-xs text-green-600">
          <span class="w-3 h-0.5 bg-green-600"></span>
          <span>Tier 3 (ML)</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-10">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>

    <div v-else-if="error" class="text-center py-10 text-red-500">
      {{ error }}
    </div>

    <div v-else class="h-[320px]">
      <v-chart ref="chartRef" :option="chartOption" autoresize class="w-full h-full" />
    </div>
    
    <div v-if="!loading && !error && !hasTier3" class="mt-2 text-xs text-center text-gray-500 italic">
      Note: Tier 3 model requires 15+ activities to activate.
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../services/api'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent])

const chartRef = ref(null)
const loading = ref(true)
const error = ref(null)
const data = ref(null)

const hasTier2 = computed(() => data.value?.has_tier2)
const hasTier3 = computed(() => data.value?.has_tier3)

const fetchData = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/performance/grade-model-comparison')
    data.value = response.data
  } catch (err) {
    console.error('Failed to fetch model comparison:', err)
    error.value = 'Failed to load comparison data'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

const chartOption = computed(() => {
  if (!data.value) return {}

  const grades = data.value.grades.map(g => Number(g.toFixed(0))) // Convert to integer percentages
  
  return {
    grid: { left: 48, right: 20, top: 24, bottom: 40 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        const grade = params[0].axisValue
        const lines = [`<strong>${grade}% Grade</strong>`]
        params.forEach(p => {
          const val = p.value
          // Format pace: 4.5 -> 4:30
          const mins = Math.floor(val)
          const secs = Math.round((val - mins) * 60)
          const timeStr = `${mins}:${secs.toString().padStart(2, '0')}`
          lines.push(`${p.marker} ${p.seriesName}: ${timeStr}/km`)
        })
        return lines.join('<br/>')
      }
    },
    legend: { 
      show: true, 
      bottom: 0,
      data: ['Tier 1 (Physics)', 'Tier 2 (Learned Params)', 'Tier 3 (ML Adjusted)']
    },
    xAxis: {
      type: 'category',
      name: 'Grade (%)',
      nameLocation: 'middle',
      nameGap: 25,
      data: grades,
      axisLabel: { 
        interval: 9, // Show every 10th label roughly (-30, -20, ...)
        color: '#6b7280' 
      },
      axisTick: { show: true },
      axisLine: { show: true },
      splitLine: { show: true, lineStyle: { color: '#f3f4f6' } }
    },
    yAxis: {
      type: 'value',
      name: 'Pace (min/km)',
      inverse: true, // Lower pace is faster (higher on graph)
      axisLabel: {
        color: '#6b7280',
        formatter: (val) => {
           const mins = Math.floor(val)
           const secs = Math.round((val - mins) * 60)
           return `${mins}:${secs.toString().padStart(2, '0')}`
        }
      },
      splitLine: { lineStyle: { color: '#e5e7eb' } }
    },
    series: [
      {
        name: 'Tier 1 (Physics)',
        type: 'line',
        data: data.value.tier1_pace,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: '#9ca3af', type: 'dashed' }, // Gray dashed
        itemStyle: { color: '#9ca3af' },
        z: 1
      },
      {
        name: 'Tier 2 (Learned Params)',
        type: 'line',
        data: data.value.tier2_pace,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: '#2563eb' }, // Blue
        itemStyle: { color: '#2563eb' },
        z: 2
      },
      {
        name: 'Tier 3 (ML Adjusted)',
        type: 'line',
        data: data.value.tier3_pace,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3, color: '#16a34a' }, // Green
        itemStyle: { color: '#16a34a' },
        z: 3
      }
    ]
  }
})
</script>
