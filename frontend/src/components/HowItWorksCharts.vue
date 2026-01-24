<template>
  <div class="space-y-12">
    <!-- Pace vs Grade Chart -->
    <div>
      <h3 class="text-lg font-bold text-slate-900 mb-4">{{ $t('howitworks.charts.pace_grade.title') }}</h3>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <v-chart :option="paceGradeOption" autoresize class="w-full h-[300px]" />
        <p class="text-xs text-slate-500 mt-3 text-center">{{ $t('howitworks.charts.pace_grade.caption') }}</p>
      </div>
    </div>

    <!-- Confidence Interval by Tier -->
    <div>
      <h3 class="text-lg font-bold text-slate-900 mb-4">{{ $t('howitworks.charts.confidence.title') }}</h3>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <v-chart :option="confidenceOption" autoresize class="w-full h-[280px]" />
        <p class="text-xs text-slate-500 mt-3 text-center">{{ $t('howitworks.charts.confidence.caption') }}</p>
      </div>
    </div>

    <!-- Fatigue Accumulation -->
    <div>
      <h3 class="text-lg font-bold text-slate-900 mb-4">{{ $t('howitworks.charts.fatigue.title') }}</h3>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <v-chart :option="fatigueOption" autoresize class="w-full h-[300px]" />
        <p class="text-xs text-slate-500 mt-3 text-center">{{ $t('howitworks.charts.fatigue.caption') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent
])

const { t } = useI18n()

// Pace vs Grade curve - based on physics model behavior
const paceGradeOption = computed(() => {
  const grades = []
  const paceRatios = []

  // Generate pace ratio curve (simplified physics model behavior)
  for (let grade = -25; grade <= 30; grade += 1) {
    grades.push(grade)

    let ratio
    if (grade >= 0) {
      // Uphill: exponential slowdown
      ratio = 1 + 0.05 * grade + 0.002 * grade * grade
    } else {
      // Downhill: faster but limited by technique
      const absGrade = Math.abs(grade)
      if (absGrade <= 10) {
        ratio = 1 - 0.02 * absGrade
      } else {
        // Very steep downhill - technique limited, slows down
        ratio = 0.8 + 0.01 * (absGrade - 10)
      }
    }
    paceRatios.push(parseFloat(ratio.toFixed(3)))
  }

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f172a',
      borderColor: 'rgba(148, 163, 184, 0.6)',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params) => {
        const grade = params[0].value[0]
        const ratio = params[0].value[1]
        const paceExample = (5 * ratio).toFixed(1)
        return `<b>Grade:</b> ${grade}%<br/><b>Pace multiplier:</b> ${ratio}x<br/><b>Example:</b> ${paceExample} min/km`
      }
    },
    grid: {
      left: 50,
      right: 30,
      top: 30,
      bottom: 50
    },
    xAxis: {
      type: 'value',
      name: t('howitworks.charts.pace_grade.x_axis'),
      nameLocation: 'middle',
      nameGap: 30,
      min: -25,
      max: 30,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } }
    },
    yAxis: {
      type: 'value',
      name: t('howitworks.charts.pace_grade.y_axis'),
      nameLocation: 'middle',
      nameGap: 35,
      min: 0.7,
      max: 3,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b', formatter: '{value}x' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#10b981', width: 3 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
          ]
        }
      },
      data: grades.map((g, i) => [g, paceRatios[i]]),
      markArea: {
        silent: true,
        data: [
          [{ xAxis: -25, itemStyle: { color: 'rgba(34, 197, 94, 0.1)' } }, { xAxis: 0 }],
          [{ xAxis: 0, itemStyle: { color: 'rgba(239, 68, 68, 0.1)' } }, { xAxis: 30 }]
        ]
      }
    }]
  }
})

// Confidence interval narrowing by tier
const confidenceOption = computed(() => {
  const tiers = [
    { name: 'Tier 1', lower: 0.88, upper: 1.12, color: '#94a3b8' },
    { name: 'Tier 2', lower: 0.92, upper: 1.08, color: '#10b981' },
    { name: 'Tier 3', lower: 0.94, upper: 1.06, color: '#f59e0b' }
  ]

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f172a',
      borderColor: 'rgba(148, 163, 184, 0.6)',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params) => {
        const tier = params[0].name
        const lower = ((1 - params[0].value) * 100).toFixed(0)
        const upper = ((params[1].value - 1) * 100).toFixed(0)
        return `<b>${tier}</b><br/>Confidence: -${lower}% to +${upper}%`
      }
    },
    grid: {
      left: 60,
      right: 30,
      top: 30,
      bottom: 40
    },
    xAxis: {
      type: 'category',
      data: tiers.map(t => t.name),
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b', fontWeight: 'bold' }
    },
    yAxis: {
      type: 'value',
      name: t('howitworks.charts.confidence.y_axis'),
      nameLocation: 'middle',
      nameGap: 45,
      min: 0.85,
      max: 1.15,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: {
        color: '#64748b',
        formatter: (val) => `${((val - 1) * 100).toFixed(0)}%`
      },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } }
    },
    series: [
      {
        name: 'Lower bound',
        type: 'bar',
        stack: 'confidence',
        itemStyle: { color: 'transparent' },
        data: tiers.map(t => t.lower)
      },
      {
        name: 'Range',
        type: 'bar',
        stack: 'confidence',
        itemStyle: {
          color: (params) => tiers[params.dataIndex].color,
          borderRadius: [4, 4, 4, 4]
        },
        data: tiers.map(t => t.upper - t.lower),
        label: {
          show: true,
          position: 'inside',
          formatter: (params) => {
            const pct = (params.value * 100).toFixed(0)
            return `±${pct / 2}%`
          },
          color: '#fff',
          fontWeight: 'bold',
          fontSize: 12
        }
      }
    ]
  }
})

// Fatigue accumulation effect
const fatigueOption = computed(() => {
  const distances = []
  const noFatigue = []
  const withFatigue = []

  // Simulate a route with significant downhill early, then uphill
  let accumulatedLoad = 0
  const basePace = 6.0 // min/km

  for (let km = 0; km <= 50; km += 2) {
    distances.push(km)

    // Simulate terrain: downhill 0-20km, flat 20-30km, uphill 30-50km
    let terrainPace
    if (km < 20) {
      // Downhill section - accumulates fatigue
      terrainPace = basePace * 0.85
      accumulatedLoad += 100 // Eccentric load
    } else if (km < 30) {
      terrainPace = basePace
    } else {
      // Uphill section
      terrainPace = basePace * 1.4
    }

    noFatigue.push(parseFloat(terrainPace.toFixed(2)))

    // With fatigue: pace degrades based on accumulated load
    const fatigueFactor = 1 + (accumulatedLoad / 50000)
    const fatiguedPace = terrainPace * fatigueFactor
    withFatigue.push(parseFloat(fatiguedPace.toFixed(2)))
  }

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f172a',
      borderColor: 'rgba(148, 163, 184, 0.6)',
      textStyle: { color: '#f8fafc', fontSize: 12 }
    },
    legend: {
      data: [t('howitworks.charts.fatigue.no_fatigue'), t('howitworks.charts.fatigue.with_fatigue')],
      top: 0,
      textStyle: { color: '#64748b' }
    },
    grid: {
      left: 50,
      right: 30,
      top: 40,
      bottom: 50
    },
    xAxis: {
      type: 'category',
      data: distances,
      name: t('howitworks.charts.fatigue.x_axis'),
      nameLocation: 'middle',
      nameGap: 30,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      name: t('howitworks.charts.fatigue.y_axis'),
      nameLocation: 'middle',
      nameGap: 35,
      inverse: true,
      min: 4,
      max: 10,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.2)' } }
    },
    series: [
      {
        name: t('howitworks.charts.fatigue.no_fatigue'),
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#94a3b8', width: 2, type: 'dashed' },
        data: noFatigue
      },
      {
        name: t('howitworks.charts.fatigue.with_fatigue'),
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ef4444', width: 3 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239, 68, 68, 0.2)' },
              { offset: 1, color: 'rgba(239, 68, 68, 0.05)' }
            ]
          }
        },
        data: withFatigue
      }
    ]
  }
})
</script>
