<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Subscription } from 'rxjs'

import { MainEvent } from '../../../../entities/main'

//service
import { useMainEventStore } from '../../../../entities/main'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import type { PointExp } from '../../../../entities/main/model/plot.store'
import { stringifyWithInfinity } from '../../../../shared/lib'

defineOptions({ name: 'SkeletonChart' })

// initialize store
const store = useMainEventStore()
const plotStore = usePlotStore()
// destructure reactive value from main.event.store
const { experiment_description, experimentFinished } = storeToRefs(store)
const { selected, visibleCharts, allRes, solution } = storeToRefs(plotStore)

const subs = new Subscription()

onMounted(() => {
    initMainEvents()
})

onUnmounted(() => {
    subs.unsubscribe()
})

// an already measured point with the same configuration and results, if any
function findMatchingPoint(configuration: any): PointExp | undefined {
    const configurations = stringifyWithInfinity(configuration.configurations)
    const results = stringifyWithInfinity(configuration.results)
    return allRes.value.find(point =>
        stringifyWithInfinity(point.configurations) === configurations &&
        stringifyWithInfinity(point.results) === results
    )
}

// the measured points of one message, appended with one change of allRes
function appendPoints(configurations: any[]): PointExp[] {
    const min = new Date().getMinutes();
    const sec = new Date().getSeconds();
    if (configurations.length === 0) return []
    const measured = allRes.value.length
    const points: PointExp[] = configurations.map((configuration: any, index: number) => ({
        'configurations': configuration.configurations,
        'results': configuration.results,
        'time': min + 'm ' + sec + 's',
        'measured points': measured + index + 1
    }))
    allRes.value = [...allRes.value, ...points]
    return points
}

function initMainEvents() {
    watch(experiment_description, () => {
        allRes.value = []
        solution.value = null
        selected.value['Optimization History'] = !!experiment_description.value?.PlotSelection?.Plot?.OptimizationHistory
        selected.value['Parallel Coordinates'] = !!experiment_description.value?.PlotSelection?.Plot?.ParallelCoordinates
        selected.value['Rank Plot'] = !!experiment_description.value?.PlotSelection?.Plot?.RankPlot
        selected.value['Hyperparameter Importances']= !!experiment_description.value?.PlotSelection?.Plot?.HyperparameterImportances
        selected.value['Slice Plot'] = !!experiment_description.value?.PlotSelection?.Plot?.SlicePlot
        selected.value['Contour Plot'] = !!experiment_description.value?.PlotSelection?.Plot?.ContourPlot
        selected.value['Pareto Front'] = !!experiment_description.value?.PlotSelection?.Plot?.ParetoFront
        selected.value['EDF Plot'] = !!experiment_description.value?.PlotSelection?.Plot?.EDFPlot
        selected.value['Heatmap'] = !!experiment_description.value?.PlotSelection?.Plot?.Heatmap
        // disabled, see the HeatmapReg import comment in App.vue
        // selected.value['Heatmap Reg'] = !!experiment_description.value?.PlotSelection?.Plot?.HeatmapReg
        visibleCharts.value = Object.entries(selected.value)
            .filter(([, enabled]) => enabled)
            .map(([name]) => name)
    }, {
        deep: true,
        immediate: true
    })

    // add start point
    subs.add(store.onEvent(MainEvent.DEFAULT)?.subscribe((message: any) => {
        if (experimentFinished.value) return
        if (message.headers['message_subtype'] === 'configuration') {
            appendPoints(message.body)
        }
    }))

    // add last point
    subs.add(store.onEvent(MainEvent.FINAL)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs: any[] = message.body
            // the solution is usually one of the measured configurations: don't count it twice
            const measured = configs.map(findMatchingPoint)
            const added = appendPoints(configs.filter((_, index) => !measured[index]))
            let next = 0
            const points = measured.map(point => point ?? added[next++])
            if (points.length > 0) solution.value = points[points.length - 1]
        }
    }))

    // add new point
    subs.add(store.onEvent(MainEvent.NEW)?.subscribe((message: any) => {
        if (experimentFinished.value) return
        if (message.headers['message_subtype'] === 'configuration') {
            // check the best availbale point
            const descr = experiment_description.value

            let objectives = descr?.['Context']?.['TaskConfiguration']?.['Objectives'] as any
            if (!objectives) return

            appendPoints(message.body)
        }
    }))
}
</script>
<template>
  <!-- Controller component -->
  <div style="display: none;" />
</template>
