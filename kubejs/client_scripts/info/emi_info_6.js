RecipeViewerEvents.addInformation('item', (event) => {
    const descriptions2 = [
        {
            filter: ['modern_industrialization:deepslate_platinum_ore'],
            text: ['This ore can generate in resource nodes found on the surface in the overworld.', ' ', 'Although rare, it can also be found in the Overworld Mining Dimension.']
        }
    ];

    descriptions2.forEach((description) => {
        event.add(description.filter, description.text);
    });
});