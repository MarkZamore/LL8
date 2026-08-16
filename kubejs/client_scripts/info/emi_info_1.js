RecipeViewerEvents.addInformation('item', (event) => {
    const descriptions = [
        {
            filter: ['tnp:limitless_sword'],
            text: ['§aExceptional!', ' ', '§a..nothing more.']
        }
    ];

    descriptions.forEach((description) => {
        event.add(description.filter, description.text);
    });
});