import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHeatmap } from '../../widgets/charts/heatmap/render'
import { theme } from '../../widgets/charts/model/heatmap-theme'
import type { PointExp } from '../../entities/main/model/plot.store'
import { N0, N1, categoricalSpecsByName } from './searchSpaceFixture'

const plotly = { react: vi.fn(), purge: vi.fn() }

const trial = (configurations: Record<string, string>, results: Record<string, number>): PointExp => ({
    configurations, results, time: '1m 0s', 'measured points': 1
})

// the flat space N0 x N1: N1 is active only under N01, so a configuration of N02 has no value for it
const n01n11 = trial({ [N0]: `${N0}.N01`, [N1]: `${N1}.N11` }, { runtime: 5, energy: 50 })
const n01n12 = trial({ [N0]: `${N0}.N01`, [N1]: `${N1}.N12` }, { runtime: 7, energy: 70 })
const n02 = trial({ [N0]: `${N0}.N02` }, { runtime: 9, energy: 90 })

interface Traces {
    surface: any
    measured: any
    star: any
    layout: any
}

describe('renderHeatmap', () => {
    const element = document.createElement('div')

    const draw = (
        trials: PointExp[], param1 = N0, param2 = N1, objective = 'runtime', solution: PointExp | null = null
    ): Traces => {
        renderHeatmap(plotly, element, trials, param1, param2, objective, categoricalSpecsByName, solution)
        const [, data, layout] = plotly.react.mock.calls.at(-1)!
        return { surface: data[0], measured: data[1], star: data[2], layout }
    }

    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('purges the plot and draws nothing without configurations', () => {
        renderHeatmap(plotly, element, [], N0, N1, 'runtime', categoricalSpecsByName, null)

        expect(plotly.purge).toHaveBeenCalledWith(element)
        expect(plotly.react).not.toHaveBeenCalled()
    })

    it('spans the vertical axis by the first parameter and the horizontal one by the second, each in the order of its categories', () => {
        const { surface } = draw([n01n11])

        expect(surface.y).toEqual(['N01', 'N02'])
        expect(surface.x).toEqual(['N11', 'N12'])
    })

    it('titles the axes by the names of the parameters and orders them as the categories', () => {
        const { surface, layout } = draw([n01n11])

        expect(layout.yaxis.title.text).toBe('N0')
        expect(layout.xaxis.title.text).toBe('N1')
        expect(layout.yaxis.categoryarray).toEqual(surface.y)
        expect(layout.xaxis.categoryarray).toEqual(surface.x)
    })

    it('puts the result of a configuration into the cell of its two values and leaves the other cells empty', () => {
        const { surface } = draw([n01n11, n01n12])

        expect(surface.z).toEqual([[5, 7], [null, null]])
    })

    it('reads the selected objective', () => {
        const { surface } = draw([n01n11, n01n12], N0, N1, 'energy')

        expect(surface.z).toEqual([[50, 70], [null, null]])
    })

    it('adds no inactive category when every configuration has both parameters', () => {
        const { surface } = draw([n01n11, n01n12])

        expect(surface.x).not.toContain('inactive')
        expect(surface.y).not.toContain('inactive')
    })

    it('draws a configuration without the second parameter in an inactive column placed first', () => {
        const { surface } = draw([n01n11, n02])

        expect(surface.x).toEqual(['inactive', 'N11', 'N12'])
        expect(surface.y).toEqual(['N01', 'N02'])
        expect(surface.z).toEqual([[null, 5, null], [9, null, null]])
    })

    it('draws a configuration without the first parameter in an inactive row placed first', () => {
        const { surface } = draw([n01n11, n02], N1, N0)

        expect(surface.y).toEqual(['inactive', 'N11', 'N12'])
        expect(surface.x).toEqual(['N01', 'N02'])
        expect(surface.z).toEqual([[null, 9], [5, null], [null, null]])
    })

    it('marks the measured configurations by crosses in their cells, the inactive ones included', () => {
        const { measured } = draw([n01n11, n02])

        expect(measured.marker.symbol).toBe('cross')
        expect(measured.x).toEqual(['N11', 'inactive'])
        expect(measured.y).toEqual(['N01', 'N02'])
    })

    it('marks the solution by a star in its cell', () => {
        const { star } = draw([n01n11, n01n12], N0, N1, 'runtime', n01n12)

        expect(star.marker.symbol).toBe('star')
        expect(star.marker.color).toBe('Gold')
        expect(star.x).toEqual(['N12'])
        expect(star.y).toEqual(['N01'])
    })

    it('marks a solution without the second parameter by a star in the inactive column', () => {
        const { star } = draw([n01n11, n02], N0, N1, 'runtime', n02)

        expect(star.x).toEqual(['inactive'])
        expect(star.y).toEqual(['N02'])
    })

    it('draws no star without a solution', () => {
        const { star } = draw([n01n11])

        expect(star.x).toEqual([])
        expect(star.y).toEqual([])
    })

    it('colours the cells by the shared colour scale', () => {
        const { surface } = draw([n01n11])

        expect(surface.colorscale).toBe(theme.value.color)
    })
})
