// The index of each category of a parameter, for the values of many configurations: one lookup per value instead of a
// scan of the categories. A value that is not a category, such as undefined for a configuration in which the parameter is
// inactive, has the index -1, as Array.indexOf gives; a category listed twice has the index of its first place.
export function categoryIndexOf(categories: readonly string[]) {
    const indexByCategory = new Map<unknown, number>()
    categories.forEach((category, index) => {
        if (!indexByCategory.has(category)) indexByCategory.set(category, index)
    })
    return (value: unknown): number => indexByCategory.get(value) ?? -1
}
