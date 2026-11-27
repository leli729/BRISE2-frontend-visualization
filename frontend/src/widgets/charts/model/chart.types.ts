import type * as PlotlyJs from 'plotly.js'

// the subset of the Plotly API used by the chart renderers; the instance itself is store.plotlyInstance
export type PlotlyInstance = Pick<typeof PlotlyJs, 'react' | 'purge'>
// what the render composable needs of it besides: to lay a plot out again at its container's size
export type ResizablePlotly = PlotlyInstance & Pick<typeof PlotlyJs, 'Plots'>

export const Color = ['Portland', 'Greens', 'Greys', 'YIGnBu',
    'RdBu', 'Jet', 'Hot', 'Picnic', 'Electric',
    'Bluered', 'YIOrRd', 'Blackbody', 'Earth'] as const

export const PlotType = [
    'heatmap', 'contour', 'surface'
] as const

export const Smooth = [
    false, "fast", "best"
] as const
