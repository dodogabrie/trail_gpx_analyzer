<template>
  <div class="w-full h-[500px]">
    <v-chart ref="chartRef" :option="chartOption" autoresize class="w-full h-full" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent
])

const props = defineProps({
  points: {
    type: Array,
    required: true
  },
  segments: {
    type: Array,
    required: true
  },
  averagePace: {
    type: Number,
    required: true
  }
})

const chartRef = ref(null)
const hoveredSegmentIndex = ref(null)

const formatPace = (paceDecimal) => {
  const minutes = Math.floor(paceDecimal)
  const seconds = Math.round((paceDecimal - minutes) * 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const setupEventListeners = () => {
  if (!chartRef.value) return

  const vueChartComponent = chartRef.value
  let chart = null

  if (vueChartComponent.chart) {
    chart = vueChartComponent.chart
  } else if (typeof vueChartComponent.getEchartsInstance === 'function') {
    chart = vueChartComponent.getEchartsInstance()
  }

  if (chart) {
    // Listen to axis pointer updates to track mouse position
    chart.on('updateAxisPointer', (event) => {
      const xAxisInfo = event.axesInfo[0]
      if (xAxisInfo && xAxisInfo.value !== undefined) {
        const distanceKm = xAxisInfo.value

        // Find which segment this distance falls into
        const segmentIndex = segmentCentersRef.value.findIndex(seg =>
          distanceKm >= seg.startKm && distanceKm <= seg.endKm
        )

        if (segmentIndex !== -1) {
          hoveredSegmentIndex.value = segmentIndex
        }
      }
    })

    chart.on('globalout', () => {
      hoveredSegmentIndex.value = null
    })
  }
}

onMounted(() => {
  nextTick(() => {
    setupEventListeners()
  })
})

// Store segment centers outside computed for use in watcher
const segmentCentersRef = ref([])

watch(hoveredSegmentIndex, (newVal, oldVal) => {
  nextTick(() => {
    // Update markArea on both plots without recreating the entire chart
    if (!chartRef.value) return

    const vueChartComponent = chartRef.value
    let chart = null

    if (vueChartComponent.chart) {
      chart = vueChartComponent.chart
    } else if (typeof vueChartComponent.getEchartsInstance === 'function') {
      chart = vueChartComponent.getEchartsInstance()
    }

    if (!chart) return

    const currentOption = chart.getOption()

    // Find the main Pace series (not Average Pace) and Elevation series
    let paceSeriesIndex = -1
    let elevationSeriesIndex = -1

    currentOption.series.forEach((series, index) => {
      if (series.name === 'Pace') {
        paceSeriesIndex = index
      } else if (series.name === 'Elevation') {
        elevationSeriesIndex = index
      }
    })

    if (newVal === null || !segmentCentersRef.value[newVal]) {
      // Clear all markAreas
      const clearUpdates = currentOption.series.map((_, index) => ({
        seriesIndex: index,
        markArea: undefined
      }))
      chart.setOption({ series: clearUpdates }, { notMerge: false, lazyUpdate: true })
      return
    }

    const segment = segmentCentersRef.value[newVal]

    // Get actual axis bounds
    const paceYAxis = currentOption.yAxis[0]
    const elevationYAxis = currentOption.yAxis[1]

    const paceMarkArea = {
      silent: true,
      itemStyle: {
        color: 'rgba(251, 191, 36, 0.4)',
        borderColor: 'rgba(251, 191, 36, 1)',
        borderWidth: 2
      },
      data: [[
        { xAxis: segment.startKm, yAxis: paceYAxis.min },
        { xAxis: segment.endKm, yAxis: paceYAxis.max }
      ]]
    }

    const elevationMarkArea = {
      silent: true,
      itemStyle: {
        color: 'rgba(251, 191, 36, 0.4)',
        borderColor: 'rgba(251, 191, 36, 1)',
        borderWidth: 2
      },
      data: [[
        { xAxis: segment.startKm, yAxis: elevationYAxis.min },
        { xAxis: segment.endKm, yAxis: elevationYAxis.max }
      ]]
    }

    // Clear markArea from all series first
    const clearUpdates = currentOption.series.map((_, index) => ({
      seriesIndex: index,
      markArea: undefined
    }))

    // Then add markArea only to Pace and Elevation series with their specific axis bounds
    const updates = [...clearUpdates]

    if (paceSeriesIndex !== -1) {
      updates[paceSeriesIndex] = {
        seriesIndex: paceSeriesIndex,
        markArea: paceMarkArea
      }
    }

    if (elevationSeriesIndex !== -1) {
      updates[elevationSeriesIndex] = {
        seriesIndex: elevationSeriesIndex,
        markArea: elevationMarkArea
      }
    }

    chart.setOption({
      series: updates
    }, { notMerge: false, lazyUpdate: true })
  })
})

const chartOption = computed(() => {
  // Calculate weighted average pace from segments
  let totalDistance = 0
  let totalTime = 0
  props.segments.forEach(segment => {
    const startKm = segment.start_km || 0
    const endKm = segment.end_km || segment.segment_km || 0
    const distance = endKm - startKm
    const pace = segment.avg_pace_min_per_km
    totalDistance += distance
    totalTime += distance * pace
  })
  const actualAveragePace = totalDistance > 0 ? totalTime / totalDistance : props.averagePace

  // Prepare elevation data from points
  const elevationData = props.points.map((p, idx) => [
    p.distance / 1000, // km
    p.elevation,
    idx
  ])

  // Prepare pace data as continuous line through segment centers
  const segmentCenters = props.segments.map(segment => {
    const startKm = segment.start_km || 0
    const endKm = segment.end_km || segment.segment_km || 0
    const centerKm = (startKm + endKm) / 2
    const pace = segment.avg_pace_min_per_km
    const grade = segment.avg_grade_percent

    // Get elevation profile for this segment
    const segmentPoints = props.points.filter(p => {
      const km = p.distance / 1000
      return km >= startKm && km <= endKm
    })
    const segmentElevations = segmentPoints.map(p => p.elevation)
    const minElev = segmentElevations.length > 0 ? Math.min(...segmentElevations) : 0
    const maxElev = segmentElevations.length > 0 ? Math.max(...segmentElevations) : 0

    return {
      distance: centerKm,
      pace,
      grade,
      startKm,
      endKm,
      elevationRange: `${minElev.toFixed(0)}m - ${maxElev.toFixed(0)}m`,
      segmentLength: endKm - startKm
    }
  })

  // Store for use in watcher
  segmentCentersRef.value = segmentCenters

  // Create continuous pace line data
  const paceLineData = segmentCenters.map(center => [
    center.distance,
    center.pace
  ])

  const paceSeries = [
    {
      name: 'Pace',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: paceLineData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: {
        color: '#3b82f6',
        width: 3
      },
      itemStyle: {
        color: (params) => {
          const center = segmentCenters[params.dataIndex]
          return getSpeedColor(center.pace, actualAveragePace)
        }
      },
      emphasis: {
        focus: 'series',
        symbolSize: 12
      }
    }
  ]

  // Calculate min/max for elevation
  const elevations = elevationData.map(d => d[1])
  const minElev = Math.min(...elevations)
  const maxElev = Math.max(...elevations)
  const elevRange = maxElev - minElev

  // Calculate min/max for pace
  const allPaces = segmentCenters.map(c => c.pace)
  const minPace = Math.min(...allPaces)
  const maxPace = Math.max(...allPaces)
  const paceRange = maxPace - minPace

  return {
    tooltip: {
      trigger: 'axis',
      position: function (point, params, dom, rect, size) {
        // point: [x, y] mouse position
        // size: {contentSize: [width, height], viewSize: [width, height]}
        const [mouseX, mouseY] = point
        const tooltipWidth = size.contentSize[0]
        const tooltipHeight = size.contentSize[1]
        const viewWidth = size.viewSize[0]

        // Position tooltip to the right of cursor by default
        let x = mouseX + 20
        let y = mouseY - tooltipHeight / 2

        // If tooltip would go off right edge, position to the left
        if (x + tooltipWidth > viewWidth) {
          x = mouseX - tooltipWidth - 20
        }

        // Keep y within bounds
        if (y < 0) y = 10
        if (y + tooltipHeight > size.viewSize[1]) {
          y = size.viewSize[1] - tooltipHeight - 10
        }

        return [x, y]
      },
      axisPointer: {
        type: 'line',
        animation: false,
        lineStyle: {
          color: '#fbbf24',
          width: 2,
          type: 'solid'
        },
        label: {
          backgroundColor: '#505765',
          formatter: (params) => {
            if (params.axisDimension === 'y' && params.axisIndex === 0) {
              return formatPace(params.value) + '/km'
            }
            if (params.axisDimension === 'x') {
              return params.value.toFixed(2) + ' km'
            }
            return params.value.toFixed(0)
          }
        }
      },
      formatter: (params) => {
        if (!Array.isArray(params)) params = [params]

        let result = ''
        params.forEach(param => {
          if (param.seriesName === 'Elevation') {
            result += `<b>Distance:</b> ${param.value[0].toFixed(2)} km<br/>`
            result += `<b>Elevation:</b> ${param.value[1].toFixed(0)} m<br/>`
          }
        })

        // Add segment info if available
        if (hoveredSegmentIndex.value !== null && segmentCentersRef.value[hoveredSegmentIndex.value]) {
          const seg = segmentCentersRef.value[hoveredSegmentIndex.value]

          result += `<br/><b>Segment:</b> ${seg.startKm.toFixed(2)} - ${seg.endKm.toFixed(2)} km<br/>`
          result += `<b>Pace:</b> ${formatPace(seg.pace)}/km<br/>`
          result += `<b>Mean Slope:</b> ${seg.grade.toFixed(1)}%<br/>`
          result += `<b>Elevation Range:</b> ${seg.elevationRange}`
        }

        return result
      }
    },
    grid: [
      {
        left: 100,
        right: 50,
        top: 60,
        height: '25%'
      },
      {
        left: 100,
        right: 50,
        top: '45%',
        height: '45%'
      }
    ],
    xAxis: [
      {
        type: 'value',
        gridIndex: 0,
        name: 'Distance (km)',
        nameLocation: 'middle',
        nameGap: 30,
        axisLabel: { show: false }
      },
      {
        type: 'value',
        gridIndex: 1,
        name: 'Distance (km)',
        nameLocation: 'middle',
        nameGap: 30
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        name: 'Pace (min/km)',
        nameLocation: 'middle',
        nameGap: 45,
        min: minPace - paceRange * 0.2,
        max: maxPace + paceRange * 0.2,
        inverse: true,
        axisLabel: {
          formatter: (value) => formatPace(value)
        }
      },
      {
        type: 'value',
        gridIndex: 1,
        name: 'Elevation (m)',
        nameLocation: 'middle',
        nameGap: 45,
        min: minElev - elevRange * 0.1,
        max: maxElev + elevRange * 0.1
      }
    ],
    series: [
      // Average pace baseline
      {
        name: 'Average Pace',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: [[0, actualAveragePace], [elevationData[elevationData.length - 1][0], actualAveragePace]],
        symbol: 'none',
        lineStyle: {
          color: '#64748b',
          type: 'dashed',
          width: 2
        }
      },
      // All pace segment series
      ...paceSeries,
      // Elevation profile
      {
        name: 'Elevation',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: elevationData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#0284c7',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.5)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0.1)' }
            ]
          }
        }
        // markArea is handled dynamically in the watcher
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1]
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 10
      }
    ]
  }
})

const getSpeedColor = (pace, avgPace) => {
  const deviation = pace - avgPace
  if (deviation > 1.5) return '#ef4444' // Very slow - red
  if (deviation > 0.5) return '#f97316' // Slow - orange
  if (deviation < -1.5) return '#22c55e' // Very fast - green
  if (deviation < -0.5) return '#84cc16' // Fast - lime
  return '#3b82f6' // Normal - blue
}
</script>

<style scoped>
/* Ensure proper rendering */
.echarts {
  width: 100%;
  height: 100%;
}
</style>
