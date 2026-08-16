StartupEvents.registry('armor_material', event => {
    event
        .create('crown')
        .defense({
            helmet: 18
        })
        .enchantmentValue(25)
        .equipSound('minecraft:item.armor.equip_diamond')
        .repairIngredient(() => Ingredient.of('minecraft:gold_ingot'))
        .toughness(16)
        .knockbackResistance(1.2)
})

StartupEvents.registry('item', event => {
    event.create('tnp:limitless_helmet', 'helmet').material('kubejs:crown')
})