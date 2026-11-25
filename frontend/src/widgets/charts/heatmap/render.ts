import type { Data, Layout } from 'plotly.js'
import type { PlotlyInstance } from '../model/chart.types'
import { theme } from '../model/heatmap-theme'
import type { PointExp } from '../../../entities/main/model/plot.store'
import type { ParameterSpec } from '../../../entities/experiment/model/experiment.model'
import { DataTransformer } from '../../../entities/experiment/lib/data.transformer'
import { axisValues } from '../../../entities/experiment/lib/search-space'
import { INACTIVE_LABEL } from '../../../entities/experiment/lib/inactive'
import { cleanIdentifier } from '../../../shared/lib'

// the label of a configuration's value on an axis; a configuration without the parameter is drawn at the inactive label
function labelOf(configuration: PointExp, parameter: string): string {
    const value = configuration.configurations[parameter]
    return value === undefined ? INACTIVE_LABEL : cleanIdentifier(value)
}

// the categories of a parameter in their order, with an inactive one placed first if a configuration lacks the parameter
function axisOf(parameter: string, trials: PointExp[], specsByName: Record<string, ParameterSpec>): string[] {
    const spec = specsByName[parameter]
    const categories = (spec ? axisValues(spec) : []).map(cleanIdentifier)
    const hasInactive = trials.some(trial => trial.configurations[parameter] === undefined)
    return hasInactive ? [INACTIVE_LABEL, ...categories] : categories
}

// the number of configurations of a cell listed in its hover
const MAX_LISTED_CONFIGURATIONS = 10

// a result in four significant digits
function formatResult(result: unknown): string {
    return typeof result === 'number' ? String(Number(result.toPrecision(4))) : String(result)
}

// the hover of a cell: the number of its configurations, then each with its active parameters and its result of the
// objective, at most MAX_LISTED_CONFIGURATIONS of them
function hoverOfCell(cell: PointExp[], objective: string): string {
    if (cell.length === 0) return ''
    const lines = [`${cell.length} configuration${cell.length === 1 ? '' : 's'}`]
    for (const trial of cell.slice(0, MAX_LISTED_CONFIGURATIONS)) {
        const parameters = Object.entries(trial.configurations)
            .map(([name, value]) => `${cleanIdentifier(name)}=${cleanIdentifier(value)}`)
            .join(', ')
        lines.push(`${parameters}: ${formatResult(trial.results[objective])}`)
    }
    if (cell.length > MAX_LISTED_CONFIGURATIONS) {
        lines.push(`and ${cell.length - MAX_LISTED_CONFIGURATIONS} more`)
    }
    return lines.join('<br>')
}

export function renderHeatmap(
    plotly: PlotlyInstance,
    element: HTMLElement,
    trials: PointExp[],
    param1: string,
    param2: string,
    objective: string,
    specsByName: Record<string, ParameterSpec>,
    solution: PointExp | null
) {
    if (trials.length === 0) {
        plotly.purge(element)
        return
    }

    const y = axisOf(param1, trials, specsByName)
    const x = axisOf(param2, trials, specsByName)

    // a cell fixes the values of two parameters only, so configurations that differ in the others share it
    const trialsOfCell = new Map<string, PointExp[]>()
    for (const trial of trials) {
        const key = `${labelOf(trial, param1)},${labelOf(trial, param2)}`
        const trialsOfThisCell = trialsOfCell.get(key)
        if (trialsOfThisCell) trialsOfThisCell.push(trial)
        else trialsOfCell.set(key, [trial])
    }
    const means = new Map<string, number>()
    trialsOfCell.forEach((cell, key) =>
        means.set(key, cell.reduce((sum, trial) => sum + trial.results[objective], 0) / cell.length))
    const hovers = y.map(yLabel => x.map(xLabel => hoverOfCell(trialsOfCell.get(`${yLabel},${xLabel}`) ?? [], objective)))

    const data: Data[] = [
        { // the cells: the mean result of the configurations at the two values, with the configurations in the hover
            type: theme.value.type as 'heatmap',
            z: DataTransformer.buildZMatrix(x, y, means),
            x,
            y,
            customdata: hovers,
            hoverongaps: false,
            hovertemplate:
                `${cleanIdentifier(param1)}: %{y}<br>` +
                `${cleanIdentifier(param2)}: %{x}<br>` +
                `${objective} (mean): %{z}<br>` +
                '%{customdata}<extra></extra>',
            colorscale: theme.value.color,
            zsmooth: theme.value.smooth as 'fast' | 'best' | false
        },
        { // measured configurations
            type: 'scatter',
            mode: 'markers',
            marker: { color: 'grey', size: 7, symbol: 'cross' },
            x: trials.map(trial => labelOf(trial, param2)),
            y: trials.map(trial => labelOf(trial, param1))
        },
        { // the solution
            type: 'scatter',
            mode: 'markers',
            hoverinfo: 'none',
            showlegend: false,
            marker: { color: 'Gold', size: 16, symbol: 'star' },
            x: solution ? [labelOf(solution, param2)] : [],
            y: solution ? [labelOf(solution, param1)] : []
        }
    ]

    const layout: Partial<Layout> = {
        margin: { l: 220 },
        title: { text: 'Heat map results' },
        autosize: true,
        showlegend: false,
        xaxis: {
            title: { text: cleanIdentifier(param2) },
            type: 'category',
            autorange: true,
            range: [-0.5, x.length - 0.5],
            showgrid: true,
            categoryorder: 'array',
            categoryarray: x
        },
        yaxis: {
            title: { text: cleanIdentifier(param1) },
            type: 'category',
            autorange: true,
            range: [-0.5, y.length - 0.5],
            showgrid: true,
            categoryorder: 'array',
            categoryarray: y
        }
    }

    plotly.react(element, data, layout)
}
