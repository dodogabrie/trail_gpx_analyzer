<template>
  <div ref="chartContainer" class="chart-container"></div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  points: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['hover', 'select'])

const chartContainer = ref(null)
let chart = null

const updateChart = (points) => {
  if (!chart) return

  const distances = points.map(p => (p.distance / 1000).toFixed(2)) // km
  const elevations = points.map(p => p.elevation)

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const point = params[0]
        return `Distance: ${point.axisValue} km<br/>Elevation: ${point.value} m`
      }
    },
    toolbox: {
      feature: {
        brush: {
          type: ['lineX', 'clear'],
          title: {
            lineX: 'Select area',
            clear: 'Clear selection'
          }
        }
      },
      left: 20,
      top: 10,
      iconStyle: {
        borderColor: '#666',
        borderWidth: 1.5
      },
      emphasis: {
        iconStyle: {
          borderColor: '#ff0000',
          borderWidth: 2.5,
          shadowBlur: 8,
          shadowColor: 'rgba(255, 0, 0, 0.5)'
        }
      }
    },
    brush: {
      xAxisIndex: 0,
      brushStyle: {
        borderWidth: 2,
        color: 'rgba(255,0,0,0.15)',
        borderColor: 'rgba(255,0,0,0.8)'
      },
      outOfBrush: {
        colorAlpha: 0.3
      },
      throttleType: 'debounce',
      throttleDelay: 300
    },
    xAxis: {
      type: 'category',
      data: distances,
      name: 'Distance (km)',
      nameLocation: 'middle',
      nameGap: 30
    },
    yAxis: {
      type: 'value',
      name: 'Elevation (m)',
      nameLocation: 'middle',
      nameGap: 50
    },
    series: [{
      type: 'line',
      data: elevations,
      smooth: true,
      lineStyle: {
        color: '#2563eb',
        width: 2
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [{
            offset: 0,
            color: 'rgba(37, 99, 235, 0.5)'
          }, {
            offset: 1,
            color: 'rgba(37, 99, 235, 0.1)'
          }]
        }
      }
    }],
    grid: {
      left: 80,
      right: 40,
      top: 50,
      bottom: 60
    }
  }

  chart.setOption(option)
}

const initChart = () => {
  chart = echarts.init(chartContainer.value)

  // Handle hover - trigger on any position in chart area
  chart.getZr().on('mousemove', (event) => {
    const pointInGrid = [event.offsetX, event.offsetY]

    if (chart.containPixel('grid', pointInGrid)) {
      const xAxisIndex = chart.convertFromPixel({ seriesIndex: 0 }, pointInGrid)[0]
      const dataIndex = Math.round(xAxisIndex)

      if (dataIndex >= 0 && dataIndex < props.points.length) {
        emit('hover', dataIndex)
      }
    } else {
      emit('hover', null)
    }
  })

  chart.getZr().on('mouseout', () => {
    emit('hover', null)
  })

  // Handle brush selection - only on brushEnd to avoid spam
  chart.on('brushEnd', (params) => {
    if (params.areas && params.areas.length > 0) {
      const area = params.areas[0]
      const coordRange = area.coordRange

      // coordRange is [startIndex, endIndex] for category axis
      const startIndex = Math.floor(coordRange[0])
      const endIndex = Math.floor(coordRange[1])

      if (startIndex >= 0 && endIndex < props.points.length) {
        emit('select', { start: startIndex, end: endIndex })
      }
    } else {
      emit('select', null)
    }
  })

  // Handle clear button click
  chart.on('brushSelected', (params) => {
    if (!params.batch || params.batch.length === 0 || !params.batch[0].areas || params.batch[0].areas.length === 0) {
      emit('select', null)
    }
  })

  // Initial render
  if (props.points && props.points.length > 0) {
    updateChart(props.points)
  }
}

onMounted(() => {
  initChart()
})

onUnmounted(() => {
  if (chart) {
    chart.dispose()
  }
})

watch(() => props.points, (newPoints) => {
  if (newPoints && newPoints.length > 0) {
    updateChart(newPoints)
  }
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 220px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
}
</style>
