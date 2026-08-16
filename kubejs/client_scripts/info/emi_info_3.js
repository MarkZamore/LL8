RecipeViewerEvents.addInformation('item', (event) => {
    const descriptions2 = [
        {
            filter: ['jamd:end_portal'],
            text: ['An End Mining Dimension. Useful for those who for example want to Quarry out large areas and dont want to ruin the The End.', ' ', 'Note: Ores spawn at all Y Levels in this Mining Dimension. So you will find the most ores at any §aY level§0. (Y level does not matter).']
        }
    ];

    descriptions2.forEach((description) => {
        event.add(description.filter, description.text);
    });
});